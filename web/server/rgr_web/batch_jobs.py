"""Cancelable isolated batch sessions with operation deadlines, observed memory limits and lazy paging."""
from __future__ import annotations

import atexit
from concurrent.futures import Future
import multiprocessing as mp
import queue
import threading
import time
from typing import Any
import uuid


def batch_worker(data, connection):
    """Keep the exact result and its output iterator in one process until cancelled or expired."""
    from .batch_session import BatchSession
    try:
        session = BatchSession(data, lambda phase: connection.send({"kind": "phase", "phase": phase}))
        first = session.page()
        connection.send({"kind": "ready", "result": session.metadata() | {"page": first}})
        while True:
            command = connection.recv()
            try:
                if command["action"] == "page":
                    value = session.page(command["offset"], command["limit"])
                elif command["action"] == "apply":
                    value = session.apply(command["choice_id"])
                else:
                    raise ValueError("Unknown batch operation")
                connection.send({"kind": "response", "request_id": command["request_id"], "value": value})
            except (ValueError, IndexError) as exc:
                connection.send({"kind": "response", "request_id": command["request_id"], "error": str(exc)})
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        connection.send({"kind": "error", "error": str(exc) or type(exc).__name__})
    finally:
        connection.close()


class BatchJob:
    """Own all communication with a worker; HTTP request threads never run the exact search."""
    def __init__(self, data, timeout = 60, idle_timeout = 1800, memory_mb = 512):
        """Start a daemon worker and a monitor, with no cross-session plan identifiers."""
        self.id = uuid.uuid4().hex
        self.timeout, self.idle_timeout, self.memory_mb = timeout, idle_timeout, memory_mb
        self.created = self.last_used = time.monotonic()
        self.lock = threading.RLock()
        self.request_lock = threading.Lock()
        self.pending: queue.Queue = queue.Queue()
        self.stopped = threading.Event()
        self.state = {"id": self.id, "status": "running", "phase": "Starting the exact batch solver"}
        context = mp.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=batch_worker, args=(data, child), daemon=True)
        self.process.start()
        child.close()
        self.thread = threading.Thread(target=self._monitor, daemon=True, name=f"batch-{self.id[:8]}")
        self.thread.start()

    def snapshot(self):
        """Return current progress without waiting for symbolic search or result enumeration."""
        with self.lock:
            return dict(self.state, elapsed_s=round(time.monotonic()-self.created, 1))

    def cancel(self, status = "cancelled", message = "Revision session stopped"):
        """Stop the worker rather than leaving a timed-out exact search consuming server resources."""
        with self.lock:
            self.state.update(status=status, error=message)
            self.stopped.set()
        if self.process.is_alive():
            self.process.terminate()

    def call(self, action, **values):
        """Queue one worker operation, letting the monitor enforce deadlines and handle cancellation."""
        if not self.request_lock.acquire(blocking=False):
            raise ValueError("Another operation is in progress for this revision. Please wait.")
        try:
            if self.snapshot()["status"] != "ready":
                raise ValueError(self.snapshot().get("error", "Wait until the solver is ready"))
            future = Future()
            self.pending.put(({"request_id": uuid.uuid4().hex, "action": action, **values}, future))
            return future.result(timeout=self.timeout+5)
        finally:
            self.request_lock.release()

    def _monitor(self):
        """Track worker messages, expire idle sessions and resolve every queued HTTP operation."""
        import psutil
        waiting = True
        started = time.monotonic()
        current = None
        try:
            while not self.stopped.is_set():
                now = time.monotonic()
                if waiting and now-started > self.timeout:
                    self.cancel("timeout", "The interactive time limit was reached. No infeasibility result is implied; try a smaller batch or a longer time limit.")
                    break
                if not waiting and now-self.last_used > self.idle_timeout:
                    self.cancel("expired", "This inactive session expired. Run the revision again to browse more choices.")
                    break
                try:
                    if psutil.Process(self.process.pid).memory_info().rss > self.memory_mb*1024**2:
                        self.cancel("memory_limit", "The interactive memory limit was reached. Try fewer variables or feedback instances.")
                        break
                except psutil.NoSuchProcess:
                    pass
                except psutil.AccessDenied:
                    self.cancel("error", "The server could not monitor the solver process")
                    break
                if not waiting:
                    try:
                        command, current = self.pending.get_nowait()
                    except queue.Empty:
                        pass
                    else:
                        self.connection.send(command)
                        waiting, started, self.last_used = True, now, now
                if self.connection.poll(0.02):
                    message = self.connection.recv()
                    with self.lock:
                        if message["kind"] == "phase":
                            self.state["phase"] = message["phase"]
                        elif message["kind"] == "ready":
                            self.state.update(status="ready", phase="Optimal choices are ready", result=message["result"])
                            waiting, self.last_used = False, now
                        elif message["kind"] == "response":
                            if current is None:
                                raise RuntimeError("Unexpected batch worker response")
                            if "error" in message:
                                current.set_exception(ValueError(message["error"]))
                            else:
                                current.set_result(message["value"])
                            current = None
                            waiting, self.last_used = False, now
                        elif message["kind"] == "error":
                            self.cancel("error", message["error"])
                elif not self.process.is_alive():
                    self.cancel("error", "The solver process stopped without completing its operation")
        except Exception as exc:
            if not self.stopped.is_set():
                self.cancel("error", str(exc) or "The solver connection closed")
        finally:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
            self.connection.close()
            error = ValueError(self.snapshot().get("error", "Session closed"))
            if current is not None and not current.done():
                current.set_exception(error)
            while not self.pending.empty():
                _, future = self.pending.get_nowait()
                future.set_exception(error)


class BatchJobs:
    """Bound concurrent sessions and keep revision workers independent of unary API requests."""
    def __init__(self, max_jobs = 4):
        """Create an empty manager without starting any processes on import."""
        self.jobs: dict[str, BatchJob] = {}
        self.lock = threading.Lock()
        self.max_jobs = max_jobs
        atexit.register(self.close)

    def start(self, data):
        """Create a session only if another interactive worker slot is available."""
        with self.lock:
            self.jobs = {key: job for key, job in self.jobs.items() if not job.stopped.is_set()}
            if len(self.jobs) >= self.max_jobs:
                raise ValueError("All interactive solver slots are in use. Stop an existing run and try again.")
            job = BatchJob(data, timeout=data.get("timeout_s", 60))
            self.jobs[job.id] = job
            return job

    def get(self, job_id):
        """Retrieve an issued session without accepting arbitrary plan payloads from the browser."""
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError("This revision session is no longer available. Run it again.")
            return self.jobs[job_id]

    def close(self):
        """Terminate workers during normal server shutdown or test cleanup."""
        with self.lock:
            for job in self.jobs.values():
                job.cancel()

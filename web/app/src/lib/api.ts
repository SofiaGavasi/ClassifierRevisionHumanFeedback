// Thin wrapper over the FastAPI backend. All requests hit /api/* and are proxied to :8000 by Vite in dev.

export type Clauses = number[][];

export interface Classifier {
  nvars: number;
  var_names: string[];
  clauses: Clauses;
}

export interface Example extends Classifier {
  id: string;
  label: string;
  mode: 'formula' | 'cnf' | 'truth';
  text: string;
  omega_hint: Record<string, boolean>;
}

export interface TraceStep {
  name: string;
  description: string;
  data: any;
}

export interface Trace {
  algorithm: string;
  steps: TraceStep[];
  sdd_dot: string;
  reasons?: Array<Record<string, boolean>>;
  nvars: number;
  var_names: string[];
  clauses: Clauses;
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

export const api = {
  parse: (mode: string, text: string) =>
    post<Classifier>('/api/parse', { mode, text }),
  random: (nvars: number, density: number, seed?: number) =>
    post<Classifier>('/api/random', { nvars, density, seed }),
  examples: async () => {
    const r = await fetch('/api/examples');
    return (await r.json()).examples as Example[];
  },
  revise: (alg: string, req: Classifier & { omega: Record<string, boolean> }) =>
    post<Trace>(`/api/revise/${alg}`, req),
  apply: (req: Classifier & { omega: Record<string, boolean>; reason: Record<string, boolean> }) =>
    post<{
      weakened_reason: Record<number, boolean>;
      accepts_omega: boolean;
      revised_dot: string;
      revised_size: number;
    }>('/api/apply', req),
};

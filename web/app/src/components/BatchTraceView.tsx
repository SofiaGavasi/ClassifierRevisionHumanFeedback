// Step through recorded solver events with the actual subset tables, bounds, witnesses and map frames.
import { useEffect, useState } from 'react';
import { BatchExecutionTrace } from '../lib/api';
import { EditableKmap } from './EditableKmap';

export function BatchTraceView({ trace, positive, negative }: { trace: BatchExecutionTrace; positive: string[]; negative: string[] }) {
  const [index, setIndex] = useState(0);
  useEffect(() => setIndex(0), [trace]);
  const event = trace.events[Math.min(index, trace.events.length - 1)];
  if (!event) return null;
  return <section className="execution-trace" aria-label="Actual batch execution trace">
    <div className="section-intro"><div><strong>Follow this run</strong><p className="muted">Recorded queries and branches for your classifier. Select a step or move through the sequence.</p></div><span className="badge">{trace.total_events} solver events</span></div>
    {trace.omitted_events > 0 && <p className="trace-limit">Showing {trace.events.length} recorded events, including the final result. {trace.omitted_events} diagnostic events were omitted by the display limit. Optimal plans remain complete.</p>}
    <div className="trace-workspace"><nav className="trace-event-list" aria-label="Batch algorithm steps">{trace.events.map((item, i) => <button type="button" key={item.id} className={`ghost trace-event-button ${i === index ? 'selected-tool' : ''}`} aria-current={i === index ? 'step' : undefined} onClick={() => setIndex(i)}><span>{item.id}</span><span>{item.title}</span></button>)}</nav>
      <div className="trace-event-detail"><div className="trace-navigation"><button type="button" className="ghost" disabled={index === 0} onClick={() => setIndex(i => i - 1)}>← Previous</button><label>Step {index + 1} of {trace.events.length}<input type="range" min={0} max={trace.events.length - 1} value={index} aria-label="Batch trace step" onChange={e => setIndex(Number(e.target.value))} /></label><button type="button" className="ghost" disabled={index >= trace.events.length - 1} onClick={() => setIndex(i => i + 1)}>Next →</button></div>
        <h3>{event.title}</h3><p>{event.summary}</p><div className="row">{event.excess !== null && <span className="badge">Exact excess E={event.excess}</span>}{event.candidate > 0 && <span className="badge">Exceptional configuration {event.candidate}</span>}</div>
        {event.rows.length > 0 && <div className="table-scroll"><table className="data-table"><thead><tr>{Array.from(new Set(event.rows.flatMap(row => Object.keys(row)))).map(key => <th key={key}>{key}</th>)}</tr></thead><tbody>{event.rows.map((row, i) => <tr key={i}>{Array.from(new Set(event.rows.flatMap(item => Object.keys(item)))).map(key => <td key={key}>{row[key] ?? ''}</td>)}</tr>)}</tbody></table></div>}
        <div className="trace-map-frames">{event.frames.map((frame, i) => <figure key={i}><figcaption>{frame.title}</figcaption><EditableKmap vars={frame.visualization.vars} accepted={frame.visualization.accepted} reasons={frame.visualization.reasons} positive={positive} negative={negative} compact label={`Trace step ${event.id}: ${frame.title}`} /></figure>)}</div>
        {event.frames.length > 0 && <p className="muted">Search-state maps show the named partial coverage or witness, rather than a completed revision. The full original and final PI families appear on the feedback and result maps.</p>}
      </div>
    </div>
  </section>;
}

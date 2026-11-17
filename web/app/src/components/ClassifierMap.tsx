// Controlled classifier scratchpad with vertical tools; the parent keeps every input representation in sync.
import { useEffect, useRef, useState } from 'react';
import { Classifier } from '../lib/api';
import { classifierViews, tableClassifier } from '../lib/inputViews';
import { EditableKmap } from './EditableKmap';

export function ClassifierMap({ value, onChange }: { value: Classifier; onChange: (value: Classifier) => void }) {
  const [names, setNames] = useState(value.var_names.join(', '));
  const [brush, setBrush] = useState<'toggle' | 'accept' | 'reject'>('toggle');
  const [error, setError] = useState(''), [history, setHistory] = useState<Classifier[]>([]);
  const latest = useRef(value); latest.current = value;
  useEffect(() => { setNames(value.var_names.join(', ')); }, [value.var_names.join(',')]);
  const change = (next: Classifier) => { const previous = latest.current; latest.current = next; setHistory(old => [...old.slice(-29), previous]); onChange(next); setError(''); };
  const accepted = classifierViews(value).accepted;
  const paint = (index: number, state: boolean) => {
    const current = latest.current, values = classifierViews(current).accepted;
    if (values[index] !== state) change(tableClassifier(current.var_names, values.map((v, i) => i === index ? state : v)));
  };
  return <div className="classifier-map-builder">
    
    <div className="row compact-controls"><label>Variables <select aria-label="Number of map variables" value={value.nvars} onChange={e => { const n = Number(e.target.value); change(tableClassifier(Array.from({ length: n }, (_, i) => String.fromCharCode(97 + i)), Array(2 ** n).fill(false))); }}>{[1, 2, 3, 4, 5, 6].map(n => <option key={n}>{n}</option>)}{value.nvars > 6 && <option value={value.nvars}>{value.nvars} (map unavailable)</option>}</select></label>
      <label className="grow">Variable names <input aria-label="Map variable names" type="text" value={names} onChange={e => setNames(e.target.value)} onBlur={() => { try { const vars = names.split(',').map(v => v.trim()); if (vars.join(',') === value.var_names.join(',')) return; if (vars.length !== value.nvars) throw new Error(`Enter ${value.nvars} comma-separated names.`); change(tableClassifier(vars, accepted)); } catch (e) { setError((e as Error).message); setNames(value.var_names.join(', ')); } }} /></label></div>
    <div className="map-with-tools"><div className="map-tools" aria-label="Classifier paint tools">
      <span className="tool-group-label">Draw the accepted region</span>{(['toggle'] as const).map(tool => <button type="button" key={tool} className={brush === tool ? 'selected-tool' : 'ghost'} aria-pressed={brush === tool} onClick={() => setBrush(tool)}>{tool === 'toggle' ? 'Toggle cells' : tool === 'accept' ? 'Paint accepted' : 'Paint rejected'}</button>)}
      <span className="tool-group-label">Edit the whole map</span>{[['Clear cells', false], ['Fill cells', true]].map(([label, state]) => <button key={String(label)} type="button" className="ghost" onClick={() => change(tableClassifier(value.var_names, accepted.map(() => !!state)))}>{label}</button>)}
      <button type="button" className="ghost" onClick={() => change(tableClassifier(value.var_names, accepted.map(v => !v)))}>⇄ Invert</button>
      <button type="button" className="ghost" disabled={!history.length} onClick={() => { const previous = history[history.length - 1]; latest.current = previous; onChange(previous); setHistory(history.slice(0, -1)); }}>↶ Undo</button>
    </div><div className="map-tool-canvas"><EditableKmap vars={value.var_names} accepted={accepted} brush={brush} onPaint={(index, state) => paint(index, state as boolean)} label="Original classifier input" />
      <p className="muted">Accepts {accepted.filter(Boolean).length} of {accepted.length} instances.</p></div></div>
    {error && <p className="error-box" role="alert">{error}</p>}
  </div>;
}

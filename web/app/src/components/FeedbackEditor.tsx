// One feedback model with row editing, strict text/file import and map painting.
import { useRef, useState } from 'react';
import { Classifier } from '../lib/api';
import { bitsKey, classifierAccepts, FeedbackSets, indexBits, parseFeedbackFile, parseInstances, validateFeedback } from '../lib/feedback';
import { EditableKmap } from './EditableKmap';
import { MapVisualization } from '../lib/mapGeometry';

export function FeedbackEditor({ classifier, feedback, onChange, visualization }: { classifier: Classifier; feedback: FeedbackSets; onChange: (value: FeedbackSets) => void; visualization?: MapVisualization }) {
  const latest = useRef(feedback);
  latest.current = feedback;
  const [mode, setMode] = useState('map'), [error, setError] = useState('');
  const [draft, setDraft] = useState<boolean[]>(Array(classifier.nvars).fill(false));
  const [target, setTarget] = useState<'positive' | 'negative'>('positive');
  const [positiveText, setPositiveText] = useState(''), [negativeText, setNegativeText] = useState('');
  const [brush, setBrush] = useState<'positive' | 'negative' | 'erase'>('positive');
  const accepted = Array.from({ length: 1 << classifier.nvars }, (_, i) => classifierAccepts(classifier.clauses, indexBits(i, classifier.nvars)));
  const change = (next: FeedbackSets) => { try { const valid = validateFeedback(next); latest.current = valid; onChange(valid); setError(''); } catch (e) { setError((e as Error).message); } };
  const remove = (values: boolean[]) => ({ positive: latest.current.positive.filter(v => bitsKey(v) !== bitsKey(values)), negative: latest.current.negative.filter(v => bitsKey(v) !== bitsKey(values)) });
  const add = (values: boolean[], label: 'positive' | 'negative' | 'erase') => {
    const next = remove(values);
    if (label !== 'erase') next[label].push(values);
    change(next);
  };
  return <div className="panel">
    <div className="section-intro"><div><strong>Tell the classifier what to accept and reject</strong><p className="muted"></p></div>
      <span className="badge">{feedback.positive.length} positive · {feedback.negative.length} negative</span></div>
    <div className="tabs">{[['map', 'Karnaugh map'], ['rows', 'Edit rows'], ['paste', 'Paste / import']].map(([id, label]) => <button key={id} className={`tab ${mode === id ? 'active' : ''}`} onClick={() => {
      if (id === 'paste') { setPositiveText(feedback.positive.map(bitsKey).join('\n')); setNegativeText(feedback.negative.map(bitsKey).join('\n')); }
      if (mode === 'paste' && id !== 'paste') { try { const next = validateFeedback({ positive: parseInstances(positiveText, classifier.var_names), negative: parseInstances(negativeText, classifier.var_names) }); const key = (value: FeedbackSets) => JSON.stringify([value.positive.map(bitsKey).sort(), value.negative.map(bitsKey).sort()]); if (key(next) !== key(feedback)) change(next); } catch (e) { setError((e as Error).message); return; } }
      setMode(id); setError('');
    }}>{label}</button>)}</div>
    {mode === 'rows' && <div className="feedback-builder"><div className="row">
      <select aria-label="Feedback target" className="compact" value={target} onChange={e => setTarget(e.target.value as typeof target)}><option value="positive">P+ Must accept</option><option value="negative">N− Must reject</option></select>
      {classifier.var_names.map((v, i) => <button className={`bit-toggle ${draft[i] ? 'on' : 'ghost'}`} key={v} aria-label={`${v} = ${Number(draft[i])}`} onClick={() => setDraft(draft.map((b, j) => i === j ? !b : b))}>{v} <b>{Number(draft[i])}</b></button>)}
      <button onClick={() => add(draft, target)}>Add instance</button></div><p className="muted">Click a variable to flip its value. Adding an existing instance updates its target.</p></div>}
    {mode === 'paste' && <div>
      <div className="two-columns"><label>Positive instances<textarea aria-label="Positive instances" placeholder={'001\n101\n# or [[0,0,1],[1,0,1]]'} value={positiveText} onChange={e => setPositiveText(e.target.value)} /></label>
        <label>Negative instances<textarea aria-label="Negative instances" placeholder={'110\n# or a=1 b=1 c=0'} value={negativeText} onChange={e => setNegativeText(e.target.value)} /></label></div>
      <p className="muted">Variable order: <b>{classifier.var_names.join(', ')}</b>. Use one bitstring per line, CSV with variable headers, JSON arrays, or complete named objects.</p>
      <div className="row"><button onClick={() => { try { change({ positive: parseInstances(positiveText, classifier.var_names), negative: parseInstances(negativeText, classifier.var_names) }); } catch (e) { setError((e as Error).message); } }}>Replace feedback from text</button>
        <label className="file-label">Import JSON or CSV<input type="file" accept=".json,.csv,.txt" onChange={async e => { const file = e.target.files?.[0]; if (!file) return; try { if (file.size > 200_000) throw new Error('Use a file smaller than 200 KB.'); change(parseFeedbackFile(await file.text(), classifier.var_names)); } catch (err) { setError((err as Error).message); } e.target.value = ''; }} /></label></div>
      <details className="explanation"><summary>File format examples</summary><pre>{JSON.stringify({ positive: [Array(classifier.nvars).fill(0)], negative: [Array(classifier.nvars).fill(1)] }, null, 2)}</pre><pre>{classifier.var_names.join(',')},label{'\n'}{Array(classifier.nvars).fill('0').join(',')},positive</pre><p className="muted">Import replaces the entire current feedback. Duplicate rows within a target are collapsed; conflicting targets are rejected.</p></details>
    </div>}
    {mode === 'map' && <div className="map-with-tools"><div className="map-tools"><span className="tool-group-label">Feedback brush</span>{(['positive', 'negative', 'erase'] as const).map(b => <button key={b} aria-pressed={brush === b} className={brush === b ? 'selected-tool' : 'ghost'} onClick={() => setBrush(b)}>{b === 'positive' ? 'P' : b === 'negative' ? 'N' : 'Erase feedback'}</button>)}<p className="muted"></p></div>
      <div className="map-tool-canvas"><EditableKmap vars={classifier.var_names} accepted={accepted} reasons={visualization?.reasons} positive={feedback.positive.map(bitsKey)} negative={feedback.negative.map(bitsKey)} brush={brush} onPaint={i => add(indexBits(i, classifier.nvars), brush)} label="Feedback map" /></div></div>}
    {error && <p className="error-box" role="alert">{error}</p>}
    <div className="feedback-chips">{(['positive', 'negative'] as const).flatMap(label => feedback[label].map(values => <span className={`feedback-chip ${label}`} key={bitsKey(values)}><b>{label === 'positive' ? 'P+' : 'N−'}</b><code>{bitsKey(values)}</code><span className="muted">originally {classifierAccepts(classifier.clauses, values) ? 'accepted' : 'rejected'}</span><button className="ghost small" aria-label={`Remove ${label} ${bitsKey(values)}`} onClick={() => change(remove(values))}>×</button></span>))}</div>
    {!feedback.positive.length && !feedback.negative.length && <p className="muted">No feedback yet. Add an instance, import a batch, or choose cells on the map.</p>}
    {!!(feedback.positive.length + feedback.negative.length) && <button className="ghost small" onClick={() => change({ positive: [], negative: [] })}>Clear feedback</button>}
  </div>;
}

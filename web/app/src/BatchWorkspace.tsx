// Exact batch workflow: inputs, cancellable compilation, pageable tied plans and verified previews.
import { useEffect, useRef, useState } from 'react';
import { api, BatchAlgorithm, BatchChoice, BatchJob, BatchPreview, BatchResult, ChoicePage, Classifier, Example } from './lib/api';
import { algorithmEligibility, bitsKey, budgetLimit, classifierAccepts, FeedbackSets, indexBits, parseBudget } from './lib/feedback';
import { InputPanel } from './components/InputPanel';
import { FeedbackEditor } from './components/FeedbackEditor';
import { EditableKmap } from './components/EditableKmap';
import { SDDView } from './components/SDDView';
import { Tex } from './lib/latex';
import { MiniRevisionMaps } from './components/MiniRevisionMaps';
import { useVisualization } from './lib/useVisualization';
import { BatchTraceView } from './components/BatchTraceView';

const algorithms: { id: BatchAlgorithm; title: string; description: string }[] = [
  { id: 'auto', title: 'Automatic', description: 'Choose ORD, negative specialization, or BERD from the feedback and bounds.' },
  { id: 'ord', title: 'ORD', description: 'Positive-only coverage with unrestricted extra gain.' },
  { id: 'negative', title: 'Negative specialization', description: 'Negative-only repair with unrestricted extra loss.' },
  { id: 'berd', title: 'BERD', description: 'Mixed feedback and general semantic bounds.' },
];

export function BatchWorkspace() {
  const [classifier, setClassifier] = useState<Classifier | null>(null), [inputId, setInputId] = useState(0);
  const originalMap = useVisualization(classifier);
  const [feedback, setFeedback] = useState<FeedbackSets>({ positive: [], negative: [] });
  const [epsilon, setEpsilon] = useState('1'), [gamma, setGamma] = useState('1');
  const [algorithm, setAlgorithm] = useState<BatchAlgorithm>('auto'), [timeout, setTimeoutValue] = useState(60);
  const [job, setJob] = useState<BatchJob | null>(null), [result, setResult] = useState<BatchResult | null>(null);
  const [page, setPage] = useState<ChoicePage | null>(null), [choices, setChoices] = useState<BatchChoice[]>([]);
  const [preview, setPreview] = useState<BatchPreview | null>(null), [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const generation = useRef(0), activeJob = useRef<string | null>(null);
  const invalidate = () => {
    generation.current++;
    if (activeJob.current) void api.cancelBatch(activeJob.current).catch(() => {});
    activeJob.current = null; setJob(null); setResult(null); setPage(null); setChoices([]); setPreview(null); setSelected(null); setError(''); setBusy(false);
  };
  useEffect(() => () => { generation.current++; if (activeJob.current) void api.cancelBatch(activeJob.current).catch(() => {}); }, []);
  useEffect(() => {
    if (!job || job.status !== 'running') return;
    let stopped = false;
    const current = generation.current;
    const tick = async () => {
      try {
        const state = await api.batchStatus(job.id);
        if (stopped || current !== generation.current) return;
        setJob(state);
        if (state.status === 'ready' && state.result) { setResult(state.result); setPage(state.result.page); setChoices(state.result.page.choices); setBusy(false); }
        else if (state.status !== 'running') { setBusy(false); setError(state.error || `Search stopped: ${state.status}`); }
      } catch (e) { if (!stopped && current === generation.current) { setBusy(false); setError((e as Error).message); } }
    };
    const timer = window.setInterval(tick, 400);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [job?.id, job?.status]);
  const load = (value: Classifier, example?: Example) => {
    invalidate();
    if (value.nvars < 1 || value.nvars > 8) { setError('The interactive batch interface supports 1 to 8 variables. Reduce the classifier before loading it.'); return; }
    setClassifier(value); setInputId(i => i + 1);
    setFeedback({ positive: example?.positive_hint || [], negative: example?.negative_hint || [] });
    setEpsilon(example?.budgets?.epsilon || '1'); setGamma(example?.budgets?.gamma || '1'); setAlgorithm('auto');
  };
  const sourceFree = classifier !== null && !Array.from({ length: 1 << classifier.nvars }, (_, i) => classifierAccepts(classifier.clauses, indexBits(i, classifier.nvars))).some(Boolean);
  let budgetError = '', eligibility: string | null = null, lossRegion = 0, gainRegion = 0, lossLimit = 0, gainLimit = 0;
  try {
    parseBudget(epsilon); parseBudget(gamma);
    eligibility = algorithmEligibility(algorithm, feedback.positive.length, feedback.negative.length, epsilon, gamma);
    if (classifier) {
      const pos = new Set(feedback.positive.map(bitsKey)), neg = new Set(feedback.negative.map(bitsKey));
      for (let i = 0; i < 1 << classifier.nvars; i++) {
        const values = indexBits(i, classifier.nvars), key = bitsKey(values);
        if (classifierAccepts(classifier.clauses, values)) { if (!neg.has(key)) lossRegion++; }
        else if (!pos.has(key)) gainRegion++;
      }
      lossLimit = budgetLimit(epsilon, lossRegion); gainLimit = budgetLimit(gamma, gainRegion);
    }
  } catch (e) { budgetError = (e as Error).message; }
  const run = async () => {
    if (!classifier || budgetError || eligibility) return;
    invalidate(); const current = generation.current; setBusy(true);
    try {
      const state = await api.startBatch({ ...classifier, ...feedback, epsilon, gamma, algorithm, timeout_s: timeout });
      if (current !== generation.current) { void api.cancelBatch(state.id).catch(() => {}); return; }
      activeJob.current = state.id; setJob(state);
    } catch (e) { if (current === generation.current) { setError((e as Error).message); setBusy(false); } }
  };
  const more = async () => {
    if (!activeJob.current || !page) return;
    const current = generation.current; setBusy(true); setError('');
    try { const next = await api.batchChoices(activeJob.current, page.next_offset); if (current === generation.current) { setPage(next); setChoices(previous => [...previous, ...next.choices]); } }
    catch (e) { if (current === generation.current) setError((e as Error).message); }
    finally { if (current === generation.current) setBusy(false); }
  };
  const select = async (choice: number) => {
    if (!activeJob.current) return;
    const current = generation.current; setBusy(true); setError('');
    try { const value = await api.batchPreview(activeJob.current, choice); if (current === generation.current) { setPreview(value); setSelected(choice); } }
    catch (e) { if (current === generation.current) setError((e as Error).message); }
    finally { if (current === generation.current) setBusy(false); }
  };
  return <div className="workspace">
    <h2>1. Classifier</h2><InputPanel framework="batch" onClassifier={c => load(c)} onExamplePicked={ex => load(ex, ex)} onClear={() => { invalidate(); setClassifier(null); setFeedback({ positive: [], negative: [] }); setEpsilon('1'); setGamma('1'); setAlgorithm('auto'); setTimeoutValue(60); setInputId(i => i + 1); }} />
    {classifier && <>
      <div className="loaded-summary"><span className="status-dot" /> Classifier loaded <span className="badge">{classifier.nvars} variables</span><code>{classifier.var_names.join(', ')}</code></div>
      <h2>2. Add your feedback</h2><FeedbackEditor key={inputId} classifier={classifier} feedback={feedback} visualization={originalMap.visualization} onChange={value => { invalidate(); setFeedback(value); }} />
      {originalMap.error && <p className="error-box">Reason outlines could not load: {originalMap.error}</p>}
      <h2>3. Set semantic bounds</h2><div className="panel"><p className="muted"></p>
        <div className="two-columns">{[{ key: 'epsilon', symbol: 'ε', title: 'Loss bound', value: epsilon, region: lossRegion, limit: lossLimit, set: setEpsilon }, { key: 'gamma', symbol: 'γ', title: 'Gain bound', value: gamma, region: gainRegion, limit: gainLimit, set: setGamma }].map(bound => <div className="bound-card" key={bound.key}>
          <label htmlFor={bound.key}><strong>{bound.symbol} · {bound.title}</strong></label><input id={bound.key} type="text" value={bound.value} onChange={e => { invalidate(); bound.set(e.target.value); }} />
          <div className="row presets">{['0', '1/2', '1'].map(v => <button className="ghost small" key={v} onClick={() => { invalidate(); bound.set(v); }}>{v === '0' ? 'Strict · 0' : v === '1' ? 'Unrestricted · 1' : 'Half · 1/2'}</button>)}</div>
          {!budgetError && <p className="muted">At most <strong>{bound.limit}</strong> of {bound.region} unrequested {bound.key === 'epsilon' ? 'accepted instances may be lost' : 'rejected instances may be gained'}.</p>}
        </div>)}</div>{budgetError && <p className="error-box" role="alert">{budgetError}</p>}
        </div>
      <h2>4. Choose an algorithm</h2><div className="panel"><div className="algorithm-grid">{algorithms.map(a => {
        let reason = ''; try { reason = sourceFree && a.id !== 'auto' ? 'Use Automatic for the original classifier with no accepted instances.' : algorithmEligibility(a.id, feedback.positive.length, feedback.negative.length, epsilon, gamma) || ''; } catch { reason = 'Enter valid semantic bounds first.'; }
        return <button className={`algorithm-card ${algorithm === a.id ? 'selected' : ''}`} key={a.id} aria-pressed={algorithm === a.id} disabled={!!reason} title={reason} onClick={() => { invalidate(); setAlgorithm(a.id); }}><strong>{a.title}{a.id === 'auto' && <span className="badge">Recommended</span>}</strong><small>{reason || a.description}</small></button>;
      })}</div>
        <details className="explanation"><summary>Search time limit</summary><label>Seconds per operation<input className="compact" type="number" min={1} max={300} value={timeout} onChange={e => { invalidate(); setTimeoutValue(Math.max(1, Math.min(300, Number(e.target.value) || 1))); }} /></label><p className="muted"></p></details>
        {eligibility && <p className="error-box">{eligibility} Select Automatic or BERD.</p>}
        {/*<div className="row run-row"><button className="primary-action" disabled={busy || !!budgetError || !!eligibility || classifier.nvars > 8} onClick={run}>{busy && !result ? 'Finding minimal changes...' : 'Find minimal changes'}</button>
        {job?.status === 'running' && <button className="ghost" onClick={invalidate}>Cancel search</button>}<span className="muted"></span></div>*/} 
        {classifier.nvars > 8 && <p className="error-box">The interactive batch interface supports up to 8 variables.</p>}
      </div> 
    </>}
    {job?.status === 'running' && <div className="progress-box" role="status"><span className="spinner" /><div><strong>{job.phase}</strong><p className="muted">{job.elapsed_s}s elapsed. Larger batches can take longer.</p></div></div>}
    {error && <p className="error-box" role="alert">{error}</p>}
    {result && <>
      <h2>5. Understand the resolution</h2><div className="result-strip"><div><small>Algorithm used</small><strong>{result.algorithm}</strong></div><div><small>Minimum structural cost</small><strong>{result.minimum_cost ?? 'Not defined'}</strong></div><div><small>Optimal source plans</small><strong>{page?.total_plans ?? 'Available lazily'}</strong></div></div>
      <BatchTraceView trace={result.trace} positive={feedback.positive.map(bitsKey)} negative={feedback.negative.map(bitsKey)} />
      <details className="explanation"><summary>Algorithm notes and verification guarantees</summary>
      {result.steps.map((step, i) => <details className="explanation resolution-step" key={i} open={i === 0}><summary><span className="step-number">{i + 1}</span>{step.title}</summary><p>{step.summary}</p><ul>{step.details.map((line, j) => <li key={j}>{line}</li>)}</ul>{step.rows.length > 0 && <div className="table-scroll"><table className="data-table"><thead><tr>{Object.keys(step.rows[0]).map(key => <th key={key}>{key}</th>)}</tr></thead><tbody>{step.rows.map((row, j) => <tr key={j}>{Object.values(row).map((value, k) => <td key={k}>{value}</td>)}</tr>)}</tbody></table></div>}</details>)}
      </details>
      <details className="explanation"><summary>Original decision diagram and solver statistics</summary><SDDView dot={result.original_dot} /><pre>{JSON.stringify(result.statistics, null, 2)}</pre></details>
      <h2>6. Choose a minimal revision</h2><p className="muted">Each choice is a source-indexed plan. Different provenance stays separate even when the resulting classifiers are equal.</p>
      {!choices.length && <p className="error-box">No admissible revision satisfies these feedback and semantic bounds.</p>}
      <div className="choice-grid">{choices.map(choice => <article className={`choice-card ${selected === choice.id ? 'selected' : ''}`} key={choice.id}><div className="section-intro"><strong>Choice {choice.id + 1}</strong><span className="badge">Cost {choice.cost ?? 'undefined'}</span></div>
        {choice.identity && <p>Keep every source reason unchanged.</p>}{choice.source_free && <p>Accept exactly the positive feedback. This boundary has no source-based structural cost.</p>}
        {choice.edits.map((edit, i) => <div className="edit-line" key={i}><code>{edit.source}</code><span>→</span><div>{edit.descendants.length ? edit.descendants.map((term, j) => <code key={j}>{term}</code>) : <span className="muted">Delete source</span>}</div><small className="muted">cost {edit.cost}</small></div>)}
        <div className="choice-metrics"><span>Unintended loss <b>{choice.loss}</b> · limit {result.loss_limit}</span><span>Unintended gain <b>{choice.gain}</b> · limit {result.gain_limit}</span></div>
        {choice.equivalent_to !== null && <p className="muted">Same classifier as choice {choice.equivalent_to + 1}; different source plan.</p>}
        <MiniRevisionMaps original={result.original_visual} revised={choice.visualization} positive={feedback.positive.map(bitsKey)} negative={feedback.negative.map(bitsKey)} label={`Batch choice ${choice.id + 1}`} />
        <button disabled={busy} className={selected === choice.id ? '' : 'ghost'} onClick={() => select(choice.id)}>{selected === choice.id ? 'Selected' : 'Select and inspect'}</button>
      </article>)}</div>
      <div className="row"><p className="muted">Showing {choices.length}{page?.total_plans !== null ? ` of ${page?.total_plans}` : ''} choices.</p>{page?.has_more && <button disabled={busy} className="ghost" onClick={more}>{busy ? 'Loading...' : 'Load more optimal choices'}</button>}</div>
    </>}
    {preview && classifier && <BatchRevisionPreview value={preview} classifier={classifier} feedback={feedback} />}
  </div>;
}

function BatchRevisionPreview({ value, classifier, feedback }: { value: BatchPreview; classifier: Classifier; feedback: FeedbackSets }) {
  const [tab, setTab] = useState('map');
  const rows = value.truth_table.rows;
  return <section className="revision-preview"><h2>7. Your updated classifier · Choice {value.choice.id + 1}</h2>
    <div className="panel"><div className="row"><span className={value.positive_success ? 'success-badge' : 'err'}>{value.positive_success ? '✓ Positive feedback satisfied' : '✗ Positive feedback failed'}</span><span className={value.negative_success ? 'success-badge' : 'err'}>{value.negative_success ? '✓ Negative feedback satisfied' : '✗ Negative feedback failed'}</span><span className="badge">{value.added_count} added · {value.removed_count} removed</span></div>
      <p className="muted">Added and removed totals include requested changes. The choice's loss and gain counts exclude those corrections.</p>
      <div className="tabs">{[['map', 'Karnaugh map'], ['truth', 'Truth table'], ['formula', 'Formulas']].map(([id, text]) => <button key={id} className={`tab ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>{text}</button>)}</div>
      {tab === 'map' && <EditableKmap vars={classifier.var_names} accepted={rows.map(r => r.old)} revised={rows.map(r => r.new)} reasons={value.visualization.reasons} positive={feedback.positive.map(bitsKey)} negative={feedback.negative.map(bitsKey)} label="Revised classifier map" />}
      {tab === 'truth' && <div className="table-scroll"><table className="data-table"><thead><tr>{classifier.var_names.map(v => <th key={v}>{v}</th>)}<th>Original</th><th>Revised</th><th>Feedback</th></tr></thead><tbody>{rows.map((row, i) => <tr className={row.old !== row.new ? row.new ? 'row-added' : 'row-removed' : ''} key={i}>{row.values.map((v, j) => <td key={j}>{Number(v)}</td>)}<td>{Number(row.old)}</td><td><b>{Number(row.new)}</b></td><td>{row.feedback === 'positive' ? 'P+ Must accept' : row.feedback === 'negative' ? 'N− Must reject' : ''}</td></tr>)}</tbody></table></div>}
      {tab === 'formula' && <div className="formula-comparison"><p className="muted">Original DNF</p><Tex src={value.original_dnf_latex} /><p className="muted">Revised DNF</p><Tex src={value.revised_dnf_latex} /><p className="muted">Revised CNF</p><Tex src={value.revised_cnf_latex} /></div>}
      <details className="explanation"><summary>Revised decision diagram (BDD)</summary><SDDView dot={value.revised_dot} /></details>
    </div>
  </section>;
}

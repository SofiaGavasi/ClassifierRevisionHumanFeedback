// Top-level page. Order: input -> omega -> algorithm -> SDD (collapsible) -> trace -> revised
import { useRef, useState } from 'react';
import { api, Classifier, Example, Trace } from './lib/api';
import { InputPanel } from './components/InputPanel';
import { OmegaPicker } from './components/OmegaPicker';
import { StepView } from './components/StepView';
import { SDDView } from './components/SDDView';
import { RevisedView } from './components/RevisedView';
import { Tex } from './lib/latex';
import { EditableKmap } from './components/EditableKmap';
import { bitsKey, classifierAccepts, indexBits } from './lib/feedback';
import { useVisualization } from './lib/useVisualization';

const ALGORITHMS = [
  { id: 'cegmhs', label: 'Enumeration of minimal reasons with cegmhs' },
];

export function UnaryWorkspace() {
  const version = useRef(0);
  const [classifier, setClassifier] = useState<Classifier | null>(null);
  const originalMap = useVisualization(classifier);
  const [omega, setOmega] = useState<Record<string, boolean>>({});
  const [algorithm, setAlgorithm] = useState('cegmhs');
  const [trace, setTrace] = useState<Trace | null>(null);
  const [applied, setApplied] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [sddOpen, setSddOpen] = useState(false);

  const onClassifier = (c: Classifier) => {
    version.current++;
    setBusy(false);
    setClassifier(c);
    setOmega(Object.fromEntries(c.var_names.map(v => [v, false])));
    setTrace(null); setApplied(null); setErr(null);
  };

  const onExample = (ex: Example) => {
    onClassifier(ex);
    if (ex.omega_hint) setOmega({ ...Object.fromEntries(ex.var_names.map(v => [v, false])), ...ex.omega_hint });
  };

  const run = async () => {
    if (!classifier) return;
    if (classifier.nvars <= 8 && !Array.from({ length: 1 << classifier.nvars }, (_, i) => classifierAccepts(classifier.clauses, indexBits(i, classifier.nvars))).some(Boolean)) {
      setErr('The unary pipeline needs an original accepted instance. Choose Batch with Automatic for the source-free boundary rule.'); setTrace(null); setApplied(null); return;
    }
    setBusy(true); setErr(null); setApplied(null);
    const current = ++version.current;
    try {
      const t = await api.revise(algorithm, { ...classifier, omega });
      if (current === version.current) setTrace(t);
    } catch (e: any) { if (current === version.current) setErr(e?.message ?? String(e)); }
    finally { if (current === version.current) setBusy(false); }
  };

  const pickReason = async (reason: Record<string, boolean>) => {
    if (!classifier) return;
    setBusy(true); setErr(null);
    const current = ++version.current;
    try {
      const res = await api.apply({ ...classifier, omega, reason });
      if (current === version.current) setApplied(res);
    } catch (e: any) { if (current === version.current) setErr(e?.message ?? String(e)); }
    finally { if (current === version.current) setBusy(false); }
  };

  return (
    <div className="workspace">
      <p className="subtitle">
         </p>

      <h2>1. Classifier</h2>
      <InputPanel onClassifier={onClassifier} onExamplePicked={onExample} onClear={() => { version.current++; setClassifier(null); setOmega({}); setTrace(null); setApplied(null); setBusy(false); setErr(null); setAlgorithm('cegmhs'); setShowDetails(false); setSddOpen(false); }} />

      {classifier && (
        <>
          <div className="panel">
            <div className="kv">
              <span className="k">variables</span>
              <span className="mono">{classifier.var_names.join(', ')}</span>
              <span className="k">clauses</span>
              <span className="mono">{classifier.clauses.map(c =>
                '(' + c.map(l => (l < 0 ? '¬' : '') + classifier.var_names[Math.abs(l) - 1]).join(' ∨ ') + ')'
              ).join(' ∧ ')}</span>
            </div>
          </div>

          <h2>2. Instance ω</h2>
          <div className="panel">
            <OmegaPicker vars={classifier.var_names} omega={omega} onChange={next => { version.current++; setBusy(false); setOmega(next); setTrace(null); setApplied(null); }} />
            <details className="explanation" open><summary>Pick the instance on a Karnaugh map</summary>
              <p className="muted"></p>
              <EditableKmap vars={classifier.var_names} accepted={classifier.nvars <= 6 ? Array.from({ length: 1 << classifier.nvars }, (_, i) => classifierAccepts(classifier.clauses, indexBits(i, classifier.nvars))) : []}
                reasons={originalMap.visualization?.reasons}
                omega={bitsKey(classifier.var_names.map(v => !!omega[v]))} brush="omega" onPaint={i => { version.current++; setBusy(false); setOmega(Object.fromEntries(classifier.var_names.map((v, j) => [v, indexBits(i, classifier.nvars)[j]]))); setTrace(null); setApplied(null); }} />
            </details>
            {originalMap.error && <p className="error-box">Reason outlines could not load: {originalMap.error}</p>}
          </div>

          <h2>3. Algorithm</h2>
          <div className="panel">
            <div className="row">
              <select value={algorithm} onChange={e => setAlgorithm(e.target.value)}>
                {ALGORITHMS.map(a => (
                  <option key={a.id} value={a.id}>{a.label}</option>
                ))}
              </select>
              <label className="row" style={{ gap: 4 }}>
                <input type="checkbox" checked={showDetails} onChange={e => setShowDetails(e.target.checked)} />
                show every intermediate step
              </label>
              <button onClick={run} disabled={busy}>{busy ? '…' : 'Run pipeline'}</button>
              {err && <span className="err">{err}</span>}
            </div>
          </div>
        </>
      )}

      {trace && (
        <>
          <h2>4. SDD of the classifier</h2>
          <div className="panel">
            <div className="row" style={{ justifyContent: 'space-between', cursor: 'pointer' }} onClick={() => setSddOpen(!sddOpen)}>
              <strong>Original SDD</strong>
              <span className="details-toggle">{sddOpen ? '− hide' : '+ show'}</span>
            </div>
            {sddOpen && <div style={{ marginTop: 8 }}><SDDView dot={trace.sdd_dot} /></div>}
          </div>

          <h2>5. Trace</h2>
          {trace.steps
            .filter(s => showDetails || ['input', 'distance', 'reasons', 'accepted'].includes(s.name))
            .map((s, i) => (
              <StepView
                key={i}
                step={s}
                dOriginalDot={trace.sdd_dot}
                originalVisual={trace.original_visual}
                omega={bitsKey(classifier ? classifier.var_names.map(v => !!omega[v]) : [])}
                onPickReason={s.name === 'reasons' ? pickReason : undefined}
              />
            ))}
        </>
      )}

      {applied && (
        <>
          <h2>6. Revised classifier</h2>
           <RevisedView applied={applied} omega={omega} />
        </>
      )}
    </div>
  );
}

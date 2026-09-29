// Top-level page. Order: input -> omega -> algorithm -> SDD (collapsible) -> trace -> revised
import { useState } from 'react';
import { api, Classifier, Example, Trace } from './lib/api';
import { InputPanel } from './components/InputPanel';
import { OmegaPicker } from './components/OmegaPicker';
import { StepView } from './components/StepView';
import { SDDView } from './components/SDDView';
import { RevisedView } from './components/RevisedView';
import { Tex } from './lib/latex';

const ALGORITHMS = [
  { id: 'cegmhs', label: 'Enumeration of minimal reasons with cegmhs' },
];

export default function App() {
  const [classifier, setClassifier] = useState<Classifier | null>(null);
  const [omega, setOmega] = useState<Record<string, boolean>>({});
  const [algorithm, setAlgorithm] = useState('cegmhs');
  const [trace, setTrace] = useState<Trace | null>(null);
  const [applied, setApplied] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [sddOpen, setSddOpen] = useState(false);

  const onClassifier = (c: Classifier) => {
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
    setBusy(true); setErr(null); setApplied(null);
    try {
      const t = await api.revise(algorithm, { ...classifier, omega });
      setTrace(t);
    } catch (e: any) { setErr(e?.message ?? String(e)); }
    finally { setBusy(false); }
  };

  const pickReason = async (reason: Record<string, boolean>) => {
    if (!classifier) return;
    setBusy(true); setErr(null);
    try {
      const res = await api.apply({ ...classifier, omega, reason });
      setApplied(res);
    } catch (e: any) { setErr(e?.message ?? String(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="app">
      <h1>Reason-guided revision of Boolean classifiers</h1>
      <p className="subtitle">
        Pick a classifier and an instance <Tex src="\omega" />. If <Tex src="\omega" /> is rejected, the pipeline computes its minimal sufficient reasons; choose one and the classifier is revised to accept <Tex src="\omega" />.
      </p>

      <h2>1. Classifier</h2>
      <InputPanel onClassifier={onClassifier} onExamplePicked={onExample} />

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
            <OmegaPicker vars={classifier.var_names} omega={omega} onChange={setOmega} />
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
                onPickReason={s.name === 'reasons' ? pickReason : undefined}
              />
            ))}
        </>
      )}

      {applied && (
        <>
          <h2>6. Revised classifier</h2>
          <RevisedView applied={applied} />
        </>
      )}
    </div>
  );
}
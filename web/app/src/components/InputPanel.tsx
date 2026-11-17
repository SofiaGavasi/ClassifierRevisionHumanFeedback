// One classifier scratchpad shared by all input tabs, with explicit loading and complete reset.
import { useEffect, useMemo, useRef, useState } from 'react';
import { api, Classifier, Example } from '../lib/api';
import { classifierViews, emptyInput, tableClassifier } from '../lib/inputViews';
import { ClassifierMap } from './ClassifierMap';

type Mode = 'kmap' | 'formula' | 'cnf' | 'truth' | 'random';

export function InputPanel({ onClassifier, onExamplePicked, onClear, framework = 'unary' }: {
  onClassifier: (value: Classifier) => void; onExamplePicked: (value: Example) => void; onClear: () => void; framework?: 'unary' | 'batch';
}) {
  const [mode, setMode] = useState<Mode>('kmap');
  const [draft, setDraft] = useState<Classifier>(emptyInput);
  const [formula, setFormula] = useState(''), [cnf, setCnf] = useState('');
  const [examples, setExamples] = useState<Example[]>([]), [err, setErr] = useState<string | null>(null), [busy, setBusy] = useState(false);
  const [rNvars, setRNvars] = useState(5), [rDensity, setRDensity] = useState(4.26), [rSeed, setRSeed] = useState<number | ''>('');
  const [resetKey, setResetKey] = useState(0), [loaded, setLoaded] = useState(false);
  const version = useRef(0), latest = useRef(draft); latest.current = draft;
  const views = useMemo(() => classifierViews(draft), [draft]);
  useEffect(() => {
    let active = true;
    api.examples(framework).then(value => { if (active) setExamples(value); }).catch(e => { if (active) setErr(e.message); });
    return () => { active = false; version.current++; };
  }, [framework]);
  const synchronize = (value: Classifier) => {
    latest.current = value; setDraft(value); const next = classifierViews(value); setFormula(next.formula); setCnf(next.cnf); setErr(null);
  };
  const currentValue = async () => {
    const current = latest.current, text = classifierViews(current);
    if ((mode === 'formula' && !formula.trim() && formula !== text.formula) || (mode === 'cnf' && !cnf.trim() && cnf !== text.cnf)) throw new Error('Enter a classifier, or use Erase input to clear the workspace.');
    if (mode === 'formula' && formula !== text.formula && formula.trim()) return api.parse('formula', formula);
    if (mode === 'cnf' && cnf !== text.cnf && cnf.trim()) return api.parse('cnf', cnf);
    return current;
  };
  const changeMode = async (next: Mode) => {
    if (next === mode || busy) return;
    const token = ++version.current; setBusy(true); setErr(null);
    try { const value = await currentValue(); if (token === version.current) { synchronize(value); setMode(next); } }
    catch (e) { if (token === version.current) setErr(formatError((e as Error).message, mode)); }
    finally { if (token === version.current) setBusy(false); }
  };
  const submit = async () => {
    const token = ++version.current; setBusy(true); setErr(null);
    try {
      const value = mode === 'random' ? await api.random(rNvars, rDensity, rSeed === '' ? undefined : Number(rSeed)) : await currentValue();
      if (framework === 'batch' && value.nvars > 8) throw new Error('The interactive batch interface supports up to 8 variables.');
      if (token !== version.current) return;
      synchronize(value); setLoaded(true); onClassifier(value);
    } catch (e) { if (token === version.current) setErr(formatError((e as Error).message, mode)); }
    finally { if (token === version.current) setBusy(false); }
  };
  const pickExample = (value: Example) => {
    version.current++; setBusy(false); synchronize(value); setLoaded(true); setResetKey(i => i + 1); onExamplePicked(value);
  };
  const reset = () => {
    version.current++; setBusy(false); synchronize(emptyInput()); setFormula(''); setCnf(''); setMode('kmap'); setLoaded(false); setRNvars(5); setRDensity(4.26); setRSeed(''); setResetKey(i => i + 1); onClear();
  };
  return <div className="row classifier-input-row" style={{ alignItems: 'stretch', gap: 12 }}>
    <div className="panel" style={{ flex: '2 1 460px', minWidth: 320 }}>
      <div className="section-intro"><button type="button" className="ghost reset-input" onClick={reset}>⌫ Erase input</button></div>
      <div className="tabs">{(['kmap', 'formula', 'cnf', 'truth', 'random'] as Mode[]).map(tab => <button type="button" key={tab} disabled={busy} className={`tab ${mode === tab ? 'active' : ''}`} onClick={() => void changeMode(tab)}>{({ kmap: 'Karnaugh map', formula: 'Formula', cnf: 'CNF', truth: 'Truth table', random: 'Random' })[tab]}</button>)}</div>
      {mode === 'kmap' && <ClassifierMap key={resetKey} value={draft} onChange={synchronize} />}
      {(mode === 'formula' || mode === 'cnf') && <><textarea aria-label={mode === 'formula' ? 'Classifier formula' : 'Classifier CNF'} value={mode === 'formula' ? formula : cnf} onChange={e => mode === 'formula' ? setFormula(e.target.value) : setCnf(e.target.value)} placeholder={mode === 'formula' ? '(a & b) | (c & ~d)' : 'a b\n~a c'} />
        <p className="muted">{mode === 'formula' ? 'Use &, |, ~, and/or/not, ∧, ∨, ¬, →, or ↔. Parentheses group expressions.' : 'One clause per line. Use ~ or - for negation and # for comments.'}</p>
        {!!draft.var_names.length && <p className="muted">Declared variables: {draft.var_names.join(', ')}. Unedited representations retain this universe, including unused features.</p>}</>}
      {mode === 'truth' && (draft.nvars <= 6 ? <TruthGrid vars={draft.var_names} labels={views.accepted} onChange={(vars, labels) => { try { synchronize(tableClassifier(vars, labels)); } catch (e) { setErr((e as Error).message); } }} /> : <p className="muted">The current classifier still has {draft.nvars} variables. The editable truth-table view supports up to 6; use its formula or CNF.</p>)}
      {mode === 'random' && <><p className="muted">The current input is retained. Generate a new seeded classifier to replace it.</p><div className="row"><label>Variables<input type="number" min={2} max={8} value={rNvars} onChange={e => setRNvars(Number(e.target.value))} /></label><label>Clause density<input type="number" step={.1} value={rDensity} onChange={e => setRDensity(Number(e.target.value))} /></label><label>Seed<input type="number" value={rSeed} placeholder="Random" onChange={e => setRSeed(e.target.value === '' ? '' : Number(e.target.value))} /></label></div><p className="muted">Current input: {draft.nvars} variables ({draft.var_names.join(', ')}).</p></>}
      <div className="row input-commit"><button type="button" className="primary-action" onClick={submit} disabled={busy}>{busy ? 'Loading...' : mode === 'random' ? 'Generate and load classifier' : 'Load classifier'}</button><span className="muted"></span></div>
      {err && <ErrorBox message={err} />}
    </div>
    <div className="panel example-panel" style={{ flex: '1 1 260px', minWidth: 240 }}><strong>Try an example</strong><p className="muted">Loads the classifier{framework === 'batch' ? ', feedback and bounds' : ' and suggested instance'}.</p>
      <div className="example-list">{examples.map(example => <button type="button" className="ghost example-button" key={example.id} onClick={() => pickExample(example)}><strong>{example.label}</strong>{example.description && <small className="example-description">{example.description}</small>}</button>)}</div>
    </div>
  </div>;
}

// ------------------------------------------------------------------ error UI

function ErrorBox({ message }: { message: string }) {
  return (
    <div style={{
      marginTop: 8, padding: '8px 10px', borderRadius: 4,
      border: '1px solid var(--danger)', background: 'rgba(176,54,31,0.08)',
      fontSize: 13,
    }}>
      <strong className="err">Couldn't parse the input.</strong>
      <div style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{message}</div>
    </div>
  );
}

function formatError(raw: string, mode: Mode): string {
  const s = raw.toLowerCase();
  if (mode === 'formula') {
    if (s.includes('invalid syntax') || s.includes('parse') || s.includes('token'))
      return `The formula is not well-formed. Check that every "(" has a matching ")", every operator has two operands, and variable names are letters/underscores.\nOriginal message: ${raw}`;
    if (s.includes('name') && s.includes('not defined'))
      return `The formula references a name that isn't a valid variable.\nOriginal message: ${raw}`;
  }
  if (mode === 'cnf' && s.includes('invalid variable name'))
    return `A clause contains something that isn't a variable name. Use letters, digits and underscores (starting with a letter or underscore); prefix with ~ or - for negation.\nOriginal message: ${raw}`;
  if (mode === 'truth' && s.includes('label'))
    return `Every row must end with 0 or 1 for the label.\nOriginal message: ${raw}`;
  return raw;
}

// ---------------------------------------------------------------------- grid

const MAX_TRUTH_VARS = 6;

function TruthGrid({
  vars, labels, onChange,
}: {
  vars: string[]; labels: boolean[];
  onChange: (vars: string[], labels: boolean[]) => void;
}) {
  const n = vars.length;
  const nRows = 1 << n;

  const rows = useMemo(() => {
    const out: boolean[][] = [];
    for (let i = 0; i < nRows; i++) {
      const bits: boolean[] = [];
      for (let j = 0; j < n; j++) bits.push(((i >> (n - 1 - j)) & 1) === 1);
      out.push(bits);
    }
    return out;
  }, [n, nRows]);

  const addVar = () => {
    if (n >= MAX_TRUTH_VARS) return;
    const suggested = nextName(vars);
    const newLabels: boolean[] = [];
    for (let i = 0; i < labels.length; i++) { newLabels.push(labels[i]); newLabels.push(labels[i]); }
    onChange([...vars, suggested], newLabels);
  };

  const removeVar = (idx: number) => {
    if (n <= 1) return;
    const bit = n - 1 - idx;
    const newLabels: boolean[] = [];
    for (let i = 0; i < labels.length; i++) if (((i >> bit) & 1) === 0) newLabels.push(labels[i]);
    onChange(vars.filter((_, i) => i !== idx), newLabels);
  };

  const renameVar = (idx: number, name: string) => {
    if (!name) return;
    const cleaned = name.replace(/[^A-Za-z0-9_]/g, '');
    if (!cleaned || vars.includes(cleaned)) return;
    const next = [...vars]; next[idx] = cleaned; onChange(next, labels);
  };

  const toggleLabel = (i: number) => { const next = [...labels]; next[i] = !next[i]; onChange(vars, next); };
  const setAll = (v: boolean) => onChange(vars, new Array(nRows).fill(v));

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <button className="ghost small" onClick={addVar} disabled={n >= MAX_TRUTH_VARS}>+ variable</button>
        <button className="ghost small" onClick={() => setAll(false)}>all labels = 0</button>
        <button className="ghost small" onClick={() => setAll(true)}>all labels = 1</button>
        <span className="muted">{nRows} row{nRows === 1 ? '' : 's'}{n >= MAX_TRUTH_VARS ? ` (cap: ${MAX_TRUTH_VARS} vars)` : ''}</span>
      </div>
      <div style={{ overflowX: 'auto', maxHeight: 340, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 4 }}>
        <table style={{ borderCollapse: 'collapse', fontSize: 13, width: '100%' }}>
          <thead style={{ position: 'sticky', top: 0, background: 'var(--panel)' }}>
            <tr>
              {vars.map((v, i) => (
                <th key={i} style={{ padding: '4px 6px', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', gap: 4, alignItems: 'center', justifyContent: 'center' }}>
                    <input type="text" value={v} onChange={e => renameVar(i, e.target.value)}
                           style={{ width: 44, textAlign: 'center', padding: '2px 4px' }} />
                    <button className="ghost small" onClick={() => removeVar(i)} disabled={n <= 1}
                            title="remove this variable" style={{ padding: '0 6px', lineHeight: 1 }}>×</button>
                  </div>
                </th>
              ))}
              <th style={{ padding: '4px 8px', borderBottom: '1px solid var(--border)', color: 'var(--muted)' }}>label</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((bits, i) => (
              <tr key={i} style={{ borderTop: '1px solid var(--border)', background: labels[i] ? 'rgba(46,160,67,0.12)' : undefined }}>
                {bits.map((b, j) => (
                  <td key={j} className="mono" style={{ padding: '3px 6px', textAlign: 'center' }}>{b ? '1' : '0'}</td>
                ))}
                <td className="mono" style={{ padding: '3px 8px', textAlign: 'center', cursor: 'pointer', fontWeight: labels[i] ? 700 : 400 }}
                    onClick={() => toggleLabel(i)}>
                  {labels[i] ? '1' : '0'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="muted" style={{ marginTop: 6 }}>
        Click a label cell to flip it. Rename variables by editing the column header.
      </div>
    </div>
  );
}

function nextName(existing: string[]): string {
  for (let i = 0; i < 26; i++) { const c = String.fromCharCode(97 + i); if (!existing.includes(c)) return c; }
  for (let i = 0; i < 1000; i++) { const n = `v${i}`; if (!existing.includes(n)) return n; }
  return `x${existing.length}`;
}

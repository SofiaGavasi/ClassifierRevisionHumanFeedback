// Input panel: two side-by-side boxes.  LEFT is manual input (formula / CNF /
// truth table / random), RIGHT is the examples picker.  On narrow viewports
// they stack.
import { useEffect, useMemo, useState } from 'react';
import { api, Classifier, Example } from '../lib/api';

type Mode = 'formula' | 'cnf' | 'truth' | 'random';

const PLACEHOLDERS: Record<'formula' | 'cnf', string> = {
  formula: '(a & b) | (c & ~d)',
  cnf: '# one clause per line, ~ or - for negation\na b\n~a c\nb ~c\n',
};

const FORMULA_HELP = (
  <>
    <p style={{ margin: '4px 0' }}>
      Write any propositional formula. All of these are accepted and can be mixed:
    </p>
    <ul style={{ margin: '4px 0 6px 18px', padding: 0 }}>
      <li><code>&</code> , <code>and</code> , <code>∧</code>     (conjunction)</li>
      <li><code>|</code> , <code>or</code> , <code>∨</code>     (disjunction)</li>
      <li><code>~</code> , <code>-</code> , <code>!</code> , <code>not</code> , <code>¬</code>     (negation)</li>
      <li><code>&gt;&gt;</code> , <code>→</code>     (implication);     <code>&lt;&gt;</code> , <code>↔</code>     (bi-implication)</li>
    </ul>
    <p style={{ margin: '4px 0' }}>
      Spacing is free: <code>(b∨¬a)∧(d∨¬a)</code> and <code>( b or not a ) and ( d or -a )</code> both work.
      CNF is derived automatically.
    </p>
  </>
);

const DEFAULT_TRUTH_VARS = ['a', 'b'];

export function InputPanel({
  onClassifier,
  onExamplePicked,
}: {
  onClassifier: (c: Classifier) => void;
  onExamplePicked: (ex: Example) => void;
}) {
  const [mode, setMode] = useState<Mode>('formula');
  const [text, setText] = useState<string>(PLACEHOLDERS.formula);
  const [examples, setExamples] = useState<Example[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [tVars, setTVars] = useState<string[]>(DEFAULT_TRUTH_VARS);
  const [tLabels, setTLabels] = useState<boolean[]>(() => new Array(1 << DEFAULT_TRUTH_VARS.length).fill(false));

  const [rNvars, setRNvars] = useState(5);
  const [rDensity, setRDensity] = useState(4.26);
  const [rSeed, setRSeed] = useState<number | ''>('');

  useEffect(() => {
    api.examples().then(setExamples).catch(() => {});
  }, []);

  const changeMode = (m: Mode) => {
    setMode(m);
    if (m === 'formula' || m === 'cnf') setText(PLACEHOLDERS[m]);
    setErr(null);
  };

  const submit = async () => {
    setErr(null); setBusy(true);
    try {
      let c: Classifier;
      if (mode === 'random') {
        c = await api.random(rNvars, rDensity, rSeed === '' ? undefined : Number(rSeed));
      } else if (mode === 'truth') {
        c = await api.parse('truth', serializeTruthGrid(tVars, tLabels));
      } else {
        c = await api.parse(mode, text);
      }
      onClassifier(c);
    } catch (e: any) {
      setErr(formatError(e?.message ?? String(e), mode));
    } finally {
      setBusy(false);
    }
  };

  const pickExample = (id: string) => {
    const ex = examples.find(x => x.id === id);
    if (!ex) return;
    setMode(ex.mode as Mode);
    if (ex.mode === 'truth') {
      const { vars, labels } = parseTruthText(ex.text);
      if (vars) { setTVars(vars); setTLabels(labels); }
    } else {
      setText(ex.text);
    }
    onExamplePicked(ex);
    setErr(null);
  };


  return (
    <div className="row" style={{ alignItems: 'stretch', gap: 12 }}>
      {/* LEFT: manual input */}
      <div className="panel" style={{ flex: '2 1 460px', minWidth: 320 }}>
        <div className="muted" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
          Type your own
        </div>

        <div className="tabs">
          {(['formula', 'cnf', 'truth', 'random'] as Mode[]).map(m => (
            <button
              key={m}
              className={'tab ' + (mode === m ? 'active' : '')}
              onClick={() => changeMode(m)}
            >
              {m === 'formula' ? 'formula' : m === 'cnf' ? 'CNF' : m === 'truth' ? 'truth table' : 'random'}
            </button>
          ))}
        </div>

        {(mode === 'formula' || mode === 'cnf') && (
          <>
            <textarea value={text} onChange={e => setText(e.target.value)} />
            <div className="muted" style={{ marginTop: 4, fontSize: 13 }}>
              {mode === 'formula' && FORMULA_HELP}
              {mode === 'cnf' && 'One clause per line; ~ or - for negation; # for comments.'}
            </div>
          </>
        )}

        {mode === 'truth' && (
          <TruthGrid vars={tVars} labels={tLabels} onVarsChange={setTVars} onLabelsChange={setTLabels} />
        )}

        {mode === 'random' && (
          <div className="row">
            <label>n vars <input type="number" min={2} max={8} value={rNvars} onChange={e => setRNvars(Number(e.target.value))} style={{ width: 70 }} /></label>
            <label>density <input type="number" step={0.1} value={rDensity} onChange={e => setRDensity(Number(e.target.value))} style={{ width: 70 }} /></label>
            <label>seed <input type="number" value={rSeed} onChange={e => setRSeed(e.target.value === '' ? '' : Number(e.target.value))} style={{ width: 90 }} placeholder="none" /></label>
          </div>
        )}

        <div className="row" style={{ marginTop: 10 }}>
          <button onClick={submit} disabled={busy}>{busy ? '...' : 'Load classifier'}</button>
        </div>
        {err && <ErrorBox message={err} />}
      </div>

      {/* RIGHT: examples */}
      <div className="panel" style={{ flex: '1 1 260px', minWidth: 240 }}>
        <div className="muted" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
          Or pick an example
        </div>
        {examples.length === 0 && <p className="muted">No examples available.</p>}
        <div style={{ maxHeight: 340, overflowY: 'auto' }}>
          {examples.map(ex => (
            <button
              key={ex.id}
              className="ghost small"
              style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 4, padding: '4px 8px' }}
              onClick={() => pickExample(ex.id)}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
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
  vars, labels, onVarsChange, onLabelsChange,
}: {
  vars: string[]; labels: boolean[];
  onVarsChange: (v: string[]) => void; onLabelsChange: (l: boolean[]) => void;
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
    onVarsChange([...vars, suggested]);
    onLabelsChange(newLabels);
  };

  const removeVar = (idx: number) => {
    if (n <= 1) return;
    const bit = n - 1 - idx;
    const newLabels: boolean[] = [];
    for (let i = 0; i < labels.length; i++) if (((i >> bit) & 1) === 0) newLabels.push(labels[i]);
    onVarsChange(vars.filter((_, i) => i !== idx));
    onLabelsChange(newLabels);
  };

  const renameVar = (idx: number, name: string) => {
    if (!name) return;
    const cleaned = name.replace(/[^A-Za-z0-9_]/g, '');
    if (!cleaned || vars.includes(cleaned)) return;
    const next = [...vars]; next[idx] = cleaned; onVarsChange(next);
  };

  const toggleLabel = (i: number) => { const next = [...labels]; next[i] = !next[i]; onLabelsChange(next); };
  const setAll = (v: boolean) => onLabelsChange(new Array(nRows).fill(v));

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

function serializeTruthGrid(vars: string[], labels: boolean[]): string {
  const n = vars.length; const nRows = 1 << n;
  const lines = [[...vars, 'label'].join(' ')];
  for (let i = 0; i < nRows; i++) {
    const bits: string[] = [];
    for (let j = 0; j < n; j++) bits.push(((i >> (n - 1 - j)) & 1).toString());
    lines.push([...bits, labels[i] ? '1' : '0'].join(' '));
  }
  return lines.join('\n') + '\n';
}

function parseTruthText(text: string): { vars: string[] | null; labels: boolean[] } {
  try {
    const lines = text.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
    if (lines.length < 2) return { vars: null, labels: [] };
    const header = lines[0].split(/[\s,|:]+/).filter(Boolean);
    const vars = header.slice(0, -1); const n = vars.length;
    const labels = new Array(1 << n).fill(false);
    for (const row of lines.slice(1)) {
      const toks = row.split(/[\s,|:]+/).filter(Boolean);
      if (toks.length !== n + 1) continue;
      let idx = 0;
      for (let j = 0; j < n; j++) idx = (idx << 1) | (toks[j] === '1' ? 1 : 0);
      labels[idx] = toks[n] === '1';
    }
    return { vars, labels };
  } catch { return { vars: null, labels: [] }; }
}

function nextName(existing: string[]): string {
  for (let i = 0; i < 26; i++) { const c = String.fromCharCode(97 + i); if (!existing.includes(c)) return c; }
  for (let i = 0; i < 1000; i++) { const n = `v${i}`; if (!existing.includes(n)) return n; }
  return `x${existing.length}`;
}
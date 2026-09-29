// Revised-classifier panel: shows the weakened reason, CNF/DNF/truth-table side-by-side with the original, and highlights the newly-accepted rows / minterms.
import { useState } from 'react';
import { Tex } from '../lib/latex';
import { SDDView } from './SDDView';

type Row = { values: boolean[]; old: boolean; new: boolean; changed: boolean };

export function RevisedView({ applied }: { applied: any }) {
  const [tab, setTab] = useState<'cnf' | 'dnf' | 'truth'>('truth');
  const tt = applied.truth_table;

  return (
    <>
      <div className="panel">
        <div className="kv">
          <span className="k">accepts ω?</span>
          <span className={applied.accepts_omega ? 'ok' : 'err'}>{applied.accepts_omega ? 'yes' : 'no (bug!)'}</span>
          <span className="k">weakened reason</span>
          <span><Tex src={applied.weakened_latex} /></span>
          <span className="k">accepted models</span>
          <span>{applied.old_count} → {applied.new_count}</span>
          <span className="k">SDD size</span>
          <span>{applied.old_size} → {applied.revised_size}</span>
          <span className="k">rows added</span>
          <span>{applied.diff.added_count}</span>
          {applied.diff.removed_count > 0 && (<>
            <span className="k err">rows removed (unexpected)</span>
            <span className="err">{applied.diff.removed_count}</span>
          </>)}
        </div>
      </div>

      <div className="panel">
        <div className="tabs">
          <button className={'tab ' + (tab === 'truth' ? 'active' : '')} onClick={() => setTab('truth')}>Truth table</button>
          <button className={'tab ' + (tab === 'dnf' ? 'active' : '')} onClick={() => setTab('dnf')}>DNF</button>
          <button className={'tab ' + (tab === 'cnf' ? 'active' : '')} onClick={() => setTab('cnf')}>CNF</button>
        </div>

        {tab === 'truth' && <TruthTable tt={tt} />}

        {tab === 'dnf' && (
          <div>
            <h4 style={{ margin: '10px 0 4px', color: 'var(--muted)' }}>original <Tex src="\Delta" /></h4>
            <div className="dnf-line"><Tex src={applied.old_dnf_latex} /></div>
            <h4 style={{ margin: '14px 0 4px', color: 'var(--muted)' }}>revised <Tex src="\Delta'" /></h4>
            <div className="dnf-line"><Tex src={applied.new_dnf_latex} /></div>
          </div>
        )}

        {tab === 'cnf' && (
          <div>
            <h4 style={{ margin: '10px 0 4px', color: 'var(--muted)' }}>original <Tex src="\Delta" /> (as loaded)</h4>
            <div className="dnf-line"><Tex src={applied.old_cnf_latex} /></div>
            <h4 style={{ margin: '14px 0 4px', color: 'var(--muted)' }}>revised <Tex src="\Delta'" /> (simplified CNF)</h4>
            <div className="dnf-line"><Tex src={applied.new_cnf_latex} /></div>
            <p className="muted" style={{ marginTop: 8 }}>
              Revised CNF is derived from the truth table via a Boolean-simplification pass, so its clause layout may differ from a naive expansion of <Tex src="\Delta \vee W" />.
            </p>
          </div>
        )}
      </div>

      <SDDView dot={applied.revised_dot} sizeHint={applied.revised_size} />
    </>
  );
}

function TruthTable({ tt }: { tt: any }) {
  if (tt.too_large) {
    return <p className="muted">Truth table skipped (n = {tt.nvars} &gt; 8 rows).</p>;
  }
  const headers: string[] = tt.headers;
  const rows: Row[] = tt.rows;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr>
            {headers.map(h => (
              <th key={h} style={{ padding: '3px 8px', color: 'var(--muted)', textAlign: 'center' }}>{h}</th>
            ))}
            <th style={{ padding: '3px 8px', color: 'var(--muted)' }}>Δ</th>
            <th style={{ padding: '3px 8px', color: 'var(--muted)' }}>Δ'</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const added = !r.old && r.new;
            const removed = r.old && !r.new;
            const bg = added ? 'rgba(46,160,67,0.15)' : removed ? 'rgba(176,54,31,0.15)' : undefined;
            return (
              <tr key={i} style={{ background: bg, borderTop: '1px solid var(--border)' }}>
                {r.values.map((v, j) => (
                    <td key={j} className="mono" style={{ padding: '2px 8px', textAlign: 'center', background: bg }}>{v ? '1' : '0'}</td>
                ))}
                <td className="mono" style={{ padding: '2px 8px', textAlign: 'center' }}>{r.old ? '1' : '0'}</td>
                <td className="mono" style={{ padding: '2px 8px', textAlign: 'center', fontWeight: added ? 700 : 400 }}>
                  {r.new ? '1' : '0'}{added ? ' ↑' : ''}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="muted" style={{ marginTop: 8 }}>
        Green rows are newly accepted by the revision. Original ω is at row {rows.findIndex(r => r.old === false && r.new === true && r.changed) + 1 || '—'} (if listed).
      </p>
    </div>
  );
}
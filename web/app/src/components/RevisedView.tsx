// Revised-classifier panel: header stats, four tabs (truth table / DNF / CNF / K-map), and the revised SDD.
import { useState } from 'react';
import { Tex } from '../lib/latex';
import { SDDView } from './SDDView';
import { EditableKmap } from './EditableKmap';
import { bitsKey } from '../lib/feedback';

type Row = { values: boolean[]; old: boolean; new: boolean; changed: boolean };

export function RevisedView({ applied, omega }: {
  applied: any;
  omega: Record<string, boolean>;
}) {
  const [tab, setTab] = useState<'kmap' | 'cnf' | 'dnf' | 'truth'>('kmap');
  const tt = applied.truth_table;
  const nvars = tt?.nvars ?? (tt?.headers?.length ?? 0);
  const canKmap = !tt?.too_large && nvars >= 1 && nvars <= 6;

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
          {canKmap && (
            <button className={'tab ' + (tab === 'kmap' ? 'active' : '')} onClick={() => setTab('kmap')}>Karnaugh map</button>
          )}
          <button className={'tab ' + (tab === 'truth' ? 'active' : '')} onClick={() => setTab('truth')}>Truth table</button>
          <button className={'tab ' + (tab === 'dnf' ? 'active' : '')} onClick={() => setTab('dnf')}>DNF</button>
          <button className={'tab ' + (tab === 'cnf' ? 'active' : '')} onClick={() => setTab('cnf')}>CNF</button>
        </div>

        {tab === 'kmap' && canKmap && (
          <EditableKmap vars={tt.headers} accepted={tt.rows.map((row: Row) => row.old)} revised={tt.rows.map((row: Row) => row.new)}
            reasons={applied.visualization?.reasons} omega={bitsKey(tt.headers.map((name: string) => !!omega[name]))} label="Revised unary classifier map" />
        )}

        {(tab === 'truth' || tab === 'kmap' && !canKmap) && <TruthTable tt={tt} />}

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
              Revised CNF is derived from the truth table via Boolean simplification, so its clause layout may differ from a naive expansion of <Tex src="\Delta \vee W" />.
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
              <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                {r.values.map((v, j) => (
                  <td key={j} className="mono" style={{ padding: '2px 8px', textAlign: 'center', background: bg }}>{v ? '1' : '0'}</td>
                ))}
                <td className="mono" style={{ padding: '2px 8px', textAlign: 'center', background: bg }}>{r.old ? '1' : '0'}</td>
                <td className="mono" style={{ padding: '2px 8px', textAlign: 'center', background: bg, fontWeight: added ? 700 : 400 }}>
                  {r.new ? '1' : '0'}{added ? ' ↑' : ''}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

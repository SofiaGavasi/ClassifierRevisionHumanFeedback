// Detailed per-μ visualization. Every sub-panel starts collapsed.
import { useEffect, useRef, useState } from 'react';
// @ts-ignore
import { graphviz } from 'd3-graphviz';
import { Tex } from '../lib/latex';

function DotView({ dot, label, height = 260 }: { dot: string; label: string; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = '';
    try { graphviz(ref.current).zoom(true).fit(true).renderDot(dot); }
    catch (e) { if (ref.current) ref.current.textContent = String(e); }
  }, [dot]);
  return (
    <div style={{ flex: 1, minWidth: 260 }}>
      <div className="muted" style={{ marginBottom: 4 }}>{label}</div>
      <div className="sdd-wrap" style={{ maxHeight: height }} ref={ref} />
    </div>
  );
}

function Panel({
  title, subtitle, defaultOpen = false, children,
}: { title: React.ReactNode; subtitle?: React.ReactNode; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="panel">
      <div className="row" style={{ justifyContent: 'space-between', cursor: 'pointer' }} onClick={() => setOpen(!open)}>
        <div><strong>{title}</strong>{subtitle && <span className="muted"> · {subtitle}</span>}</div>
        <span className="details-toggle">{open ? '− hide' : '+ show'}</span>
      </div>
      {open && <div style={{ marginTop: 8 }}>{children}</div>}
    </div>
  );
}

export function MuBlock({ idx, block, dOriginalDotFallback }: {
  idx: number; block: any; dOriginalDotFallback?: string;
}) {
  const [muOpen, setMuOpen] = useState(false);
  const [iterIdx, setIterIdx] = useState(0);
  const iters = block.iterations as any[];
  const cur = iters[iterIdx];

  return (
    <div className="panel" style={{ margin: '10px 0', borderLeft: '3px solid var(--accent)' }}>
      <div className="row" style={{ justifyContent: 'space-between', cursor: 'pointer' }} onClick={() => setMuOpen(!muOpen)}>
        <div>
          <span className="mono">μ<sub>{idx}</sub></span>{' = '}<Tex src={block.mu_latex} />
          <span className="muted"> · {block.pis.length} PI{block.pis.length === 1 ? '' : 's'} found</span>
        </div>
        <span className="details-toggle">{muOpen ? '− hide details' : '+ show details'}</span>
      </div>

      {muOpen && (
        <div style={{ marginTop: 10 }}>
          <Panel
            title={<><Tex src="F_\mu" />: fixed disagreement literals</>}
            subtitle={<>size {block.F_mu.size} · <Tex src={`d^\\star = ${block.F_mu.d_star}`} /></>}
          >
            <div><Tex src={`F_\\mu = ${block.F_mu.latex}`} /></div>
            <p className="muted" style={{ marginTop: 6 }}>
              Every PI contained in a nearest <Tex src="\mu" /> must contain these literals (Lemma F-mandatory).
            </p>
          </Panel>

          <Panel
            title={<><Tex src="D_\mu = D \mid F_\mu" />: conditioned residual</>}
            subtitle={<>size {block.D_mu.size}</>}
          >
            <div className="row" style={{ alignItems: 'stretch' }}>
              {dOriginalDotFallback && <DotView dot={dOriginalDotFallback} label="original D" />}
              <DotView dot={block.D_mu.dot} label={`D_μ (${block.D_mu.size} nodes)`} />
            </div>
            <div style={{ marginTop: 8 }} className="kv">
              <span className="k">vars in support</span>
              <span className="mono">{block.D_mu.vars_in_support.join(', ') || '∅'}</span>
              <span className="k">vars dropped</span>
              <span className="mono">{block.D_mu.vars_dropped.join(', ') || '∅'}</span>
            </div>
          </Panel>

          <Panel
            title={<><Tex src="O_\mu" />: optional candidates after support reduction</>}
            subtitle={`size ${block.O_mu.size}`}
          >
            <div><Tex src={`O_\\mu = ${block.O_mu.latex}`} /></div>
            {block.O_mu.dropped_by_support_latex !== '\\emptyset' && (
              <div className="muted" style={{ marginTop: 4 }}>
                dropped by support reduction: <Tex src={block.O_mu.dropped_by_support_latex} />
              </div>
            )}
          </Panel>

          <Panel
            title={<><Tex src="N_\mu" />: necessary conditions</>}
            subtitle={`size ${block.N_mu.size}`}
          >
            <div><Tex src={`N_\\mu = ${block.N_mu.latex}`} /></div>
            <p className="muted" style={{ marginTop: 6 }}>
              Per-literal check: <Tex src="\ell \in N_\mu \iff O_\mu \setminus \{\ell\} \not\models D_\mu" />.
            </p>
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: 'var(--muted)' }}>
                  <th style={{ padding: '2px 6px' }}>ℓ</th>
                  <th style={{ padding: '2px 6px' }}><Tex src="O_\mu \setminus \{\ell\} \models D_\mu?" /></th>
                  <th style={{ padding: '2px 6px' }}>necessary</th>
                </tr>
              </thead>
              <tbody>
                {block.N_mu.witnesses.map((w: any, i: number) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '2px 6px' }}><Tex src={w.literal_latex} /></td>
                    <td style={{ padding: '2px 6px' }}>
                      <span className={w.reduced_entails ? 'ok' : 'err'}>{w.reduced_entails ? 'yes' : 'no'}</span>
                    </td>
                    <td style={{ padding: '2px 6px' }}>{w.in_N ? '✓' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel
            title={<><Tex src="U_\mu = O_\mu \setminus N_\mu" />: search space</>}
            subtitle={<><Tex src={`r_\\mu = ${block.U_mu.size}`} /></>}
          >
            <div><Tex src={`U_\\mu = ${block.U_mu.latex}`} /></div>
          </Panel>

          <Panel
            title="Counterexample-guided minimal hitting-set search"
            subtitle={`${iters.length} iteration${iters.length === 1 ? '' : 's'}` + (block.truncated_reason ? ` · truncated: ${block.truncated_reason}` : '')}
          >
            {iters.length === 0 && <p className="muted">No iterations (search terminated immediately).</p>}
            {iters.length > 0 && (
              <>
                <div className="row" style={{ marginBottom: 10 }}>
                  <button className="ghost small" disabled={iterIdx === 0} onClick={() => setIterIdx(i => Math.max(0, i - 1))}>← prev</button>
                  <input type="range" min={0} max={iters.length - 1} value={iterIdx}
                         onChange={e => setIterIdx(Number(e.target.value))}
                         style={{ flex: 1, minWidth: 200 }} />
                  <button className="ghost small" disabled={iterIdx === iters.length - 1} onClick={() => setIterIdx(i => Math.min(iters.length - 1, i + 1))}>next →</button>
                  <span className="muted">iteration {iterIdx + 1} / {iters.length}</span>
                </div>
                <IterationCard step={cur} />
                <div className="muted" style={{ marginTop: 10, fontSize: 12 }}>
                  After this step: <Tex src={`|\\mathcal{E}| = ${cur.conflict_family_size}`} />, <Tex src={`|\\mathcal{B}| = ${cur.blocked_family_size}`} />
                </div>
              </>
            )}
          </Panel>

          <Panel title="PIs contained in μ" subtitle={`${block.pis.length} found`}>
            {block.pis.map((pi: any, j: number) => (
              <div key={j} className="reason-card"><Tex src={pi.latex} /></div>
            ))}
          </Panel>
        </div>
      )}
    </div>
  );
}

function IterationCard({ step }: { step: any }) {
  return (
    <div className="panel" style={{ background: 'var(--bg)' }}>
      <div className="kv">
        <span className="k">candidate <Tex src="A" /></span>
        <span><Tex src={step.A_latex} /> <span className="muted">(size {step.A_size})</span></span>
        <span className="k">verdict</span>
        <span className={step.verdict === 'yield' ? 'ok' : 'err'}>
          {step.verdict === 'yield'
            ? <><Tex src="N_\mu \cup A \models D_\mu" /> — yield PI</>
            : <><Tex src="N_\mu \cup A \not\models D_\mu" /> — new conflict</>}
        </span>
        {step.verdict === 'yield' && (<>
          <span className="k">yielded <Tex src="\tau" /></span>
          <span><Tex src={step.tau_latex} /></span>
          <span className="k">blocked</span>
          <span><Tex src={step.blocked_added_latex} /></span>
        </>)}
        {step.verdict === 'conflict' && (<>
          <span className="k">countermodel <Tex src="\nu" /></span>
          <span className="mono">{Object.entries(step.nu).map(([k, v]) => `${k}=${v ? 'T' : 'F'}`).join(', ') || '∅'}</span>
          <span className="k">conflict <Tex src="E_\nu" /></span>
          <span><Tex src={step.conflict_latex} /></span>
        </>)}
      </div>
    </div>
  );
}
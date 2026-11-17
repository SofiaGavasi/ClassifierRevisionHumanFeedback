// Accessible Gray-code maps for painting classifiers, picking unary instances and marking batch feedback.
import { ReactNode, RefObject, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { bitsKey, indexBits, mapPanels } from '../lib/feedback';
import { reasonColor, reasonColorIndex, reasonRectangles, VisualReason } from '../lib/mapGeometry';
const NO_REASONS: VisualReason[] = [];

export function EditableKmap({ vars, accepted, revised, positive = [], negative = [], omega, brush = 'toggle', onPaint, label = 'Karnaugh map', reasons = NO_REASONS, compact = false }: {
  vars: string[]; accepted: boolean[]; revised?: boolean[]; positive?: string[]; negative?: string[]; omega?: string;
  brush?: 'toggle' | 'accept' | 'reject' | 'positive' | 'negative' | 'erase' | 'omega';
  onPaint?: (index: number, value: boolean | string) => void; label?: string;
  reasons?: VisualReason[]; compact?: boolean;
}) {
  const dragging = useRef<boolean | string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set()), [active, setActive] = useState<string | null>(null);
  useEffect(() => { setHidden(new Set()); setActive(null); }, [reasons]);
  useEffect(() => {
    const end = () => { dragging.current = null; };
    window.addEventListener('pointerup', end); window.addEventListener('pointercancel', end);
    return () => { window.removeEventListener('pointerup', end); window.removeEventListener('pointercancel', end); };
  }, []);
  if (vars.length < 1 || vars.length > 6) return <p className="muted">Map editing is available for 1 to 6 variables. Use rows or pasted instances for larger classifiers.</p>;
  const panels = mapPanels(vars.length), inner = Math.min(vars.length, 4);
  const paint = (index: number, begin: boolean) => {
    if (!onPaint) return;
    if (begin) dragging.current = brush === 'toggle' ? !accepted[index] : brush === 'accept' ? true : brush === 'reject' ? false : brush;
    if (dragging.current !== null) onPaint(index, dragging.current);
  };
  return <div className={`editable-kmap ${compact ? 'compact-map' : ''}`} aria-label={label}>
    <div className="map-legend"><span><i className="legend-accepted" /> Accepted originally</span>
      {revised && <><span><i className="legend-added" /> Added</span><span><i className="legend-removed" /> Removed</span></>}
      {(positive.length > 0 || negative.length > 0 || ['positive', 'negative', 'erase'].includes(brush)) && <><span><b className="point-positive">P+</b> Must accept</span><span><b className="point-negative">N−</b> Must reject</span></>}
      {omega !== undefined && <span>◎ Selected instance</span>}</div>
    <div className="kmap-panels">{panels.map((panel, panelIndex) => <div className="kmap-panel" key={panelIndex}>
      {panel.outer.length > 0 && <p className="map-panel-title">{panel.outer.map((v, i) => `${vars[inner + i]} = ${Number(v)}`).join(', ')}</p>}
      <KmapSurface n={vars.length} panelIndex={panelIndex} reasons={reasons} hidden={hidden} active={active} compact={compact}>
      <table className="paint-map" aria-label={`${label}${panel.outer.length ? ` panel ${panelIndex + 1}` : ''}`}>
        <thead><tr><th scope="col" className="map-axis">{vars.slice(0, panel.rowBits).join(', ') || '·'}<br /><span>↓ / → {vars.slice(panel.rowBits, inner).join(', ')}</span></th>
          {panel.columns.map(col => <th scope="col" key={col}>{col.toString(2).padStart(panel.colBits, '0')}</th>)}</tr></thead>
        <tbody>{panel.rows.map((row, ri) => <tr key={row}><th scope="row">{panel.rowBits ? row.toString(2).padStart(panel.rowBits, '0') : '·'}</th>
          {panel.indices[ri].map(index => {
            const values = indexBits(index, vars.length), bits = bitsKey(values), old = !!accepted[index], next = revised ? !!revised[index] : old;
            const target = positive.includes(bits) ? 'positive' : negative.includes(bits) ? 'negative' : null;
            const changed = revised && old !== next;
            const description = `${vars.map((v, i) => `${v}=${Number(values[i])}`).join(', ')}; original ${old ? 'accepts' : 'rejects'}${revised ? `; revised ${next ? 'accepts' : 'rejects'}` : ''}${target ? `; ${target} feedback` : ''}`;
            return <td key={index}><button type="button" className={`paint-cell ${old ? 'is-accepted' : ''} ${changed ? next ? 'is-added' : 'is-removed' : ''} ${omega === bits ? 'is-omega' : ''} ${target ? `has-${target}` : ''}`}
              aria-label={description} aria-pressed={onPaint ? brush === 'omega' ? omega === bits : target ? true : old : undefined} title={description}
              disabled={!onPaint} onPointerDown={event => { event.preventDefault(); paint(index, true); }} onPointerEnter={() => paint(index, false)}
              onClick={event => { if (event.detail === 0) { paint(index, true); dragging.current = null; } }}>
              <span>{Number(next)}</span><small className="cell-bits">{bits}</small>
              {target && <b className={`cell-target point-${target}`}>{target === 'positive' ? 'P+' : 'N−'}</b>}
              {omega === bits && <span className="omega-marker">◎</span>}
            </button></td>;
          })}</tr>)}</tbody>
      </table>
      </KmapSurface>
    </div>)}</div>
    {reasons.length > 0 && <details className="pi-legend" open={!compact}><summary>{reasons.length} prime reason{reasons.length === 1 ? '' : 's'} · colour outlines</summary>
      
      <div className="row"><button type="button" className="ghost small" onClick={() => setHidden(new Set())}>Show all</button><button type="button" className="ghost small" onClick={() => setHidden(new Set(reasons.map(r => r.id)))}>Hide outlines</button></div>
      <div className="pi-reason-list">{reasons.map(reason => <button key={reason.id} type="button" className={`pi-reason ${hidden.has(reason.id) ? 'is-hidden' : ''}`} aria-pressed={!hidden.has(reason.id)}
        style={{ borderColor: reasonColor(reasonColorIndex(reason.states)) }} onMouseEnter={() => setActive(reason.id)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(reason.id)} onBlur={() => setActive(null)}
        onClick={() => setHidden(current => { const next = new Set(current); if (next.has(reason.id)) next.delete(reason.id); else next.add(reason.id); return next; })}>
        <i style={{ background: reasonColor(reasonColorIndex(reason.states)) }} /><b>{reason.id}</b> {reason.text}</button>)}</div>
    </details>}
    {reasons !== NO_REASONS && reasons.length === 0 && (revised || accepted).every(v => !v) && <p className="muted">No prime reasons: this classifier accepts no instances.</p>}
  </div>;
}

function KmapSurface({ n, panelIndex, reasons, hidden, active, compact, children }: {
  n: number; panelIndex: number; reasons: VisualReason[]; hidden: Set<string>; active: string | null; compact: boolean; children: ReactNode;
}) {
  const surface = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<{ width: number; height: number; cells: { x: number; y: number; width: number; height: number }[] } | null>(null);
  useLayoutEffect(() => {
    const element = surface.current;
    if (!element) return;
    const measure = () => {
      const parent = element.getBoundingClientRect();
      const cells = Array.from(element.querySelectorAll('tbody td')).map(cell => { const rect = cell.getBoundingClientRect(); return { x: rect.left - parent.left, y: rect.top - parent.top, width: rect.width, height: rect.height }; });
      setLayout({ width: parent.width, height: parent.height, cells });
    };
    measure(); const observer = new ResizeObserver(measure); observer.observe(element);
    return () => observer.disconnect();
  }, [n, panelIndex, compact]);
  return <div className="kmap-surface" ref={surface as RefObject<HTMLDivElement>}>{children}
    {layout && layout.width > 0 && layout.height > 0 && reasons.length > 0 && <svg className="pi-outlines" viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" aria-label="Prime reason rectangle outlines">
      {reasons.flatMap((reason, i) => hidden.has(reason.id) ? [] : reasonRectangles(n, panelIndex, reason.states).map((rect, j) => {
        const columns = mapPanels(n)[panelIndex].columns.length;
        const start = layout.cells[rect.row * columns + rect.column], end = layout.cells[(rect.row + rect.rows - 1) * columns + rect.column + rect.columns - 1];
        if (!start || !end) return null;
        const inset = (compact ? 1.5 : 3) + (i % 4) * (compact ? .65 : 1.25);
        const x = start.x + inset, y = start.y + inset, width = Math.max(2, end.x + end.width - start.x - 2 * inset), height = Math.max(2, end.y + end.height - start.y - 2 * inset);
        return <g key={`${reason.id}-${j}`} opacity={active && active !== reason.id ? .12 : 1} data-reason={reason.id} data-wrap={rect.wrap || undefined}><title>{reason.id}: {reason.text}{rect.wrap ? ' (wraps across map edges)' : ''}</title>
          <rect x={x} y={y} width={width} height={height} rx={compact ? 2 : 4} fill="none" stroke={reasonColor(reasonColorIndex(reason.states))} strokeWidth={active === reason.id ? 3.2 : compact ? 1.7 : 2.2} />
          {active === reason.id && <text x={x + 4} y={y + 12} fill={reasonColor(reasonColorIndex(reason.states))} fontSize={10} fontWeight={750}>{reason.id}</text>}
        </g>;
      }))}
    </svg>}
  </div>;
}

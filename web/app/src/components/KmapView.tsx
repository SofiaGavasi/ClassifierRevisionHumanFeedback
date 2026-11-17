// Revised-classifier Gray maps show original acceptance, changes and the selected instance.
// Supports 1..6 variables. For 5 the map is split into two 4-var halves
// (var 5 = 0 | var 5 = 1); for 6 it is a 2x2 grid of 4-var halves.
// Larger n is unreadable as a K-map and shows a note instead.
import { Fragment } from 'react';

type Row = { values: boolean[]; old: boolean; new: boolean };

const GRAY2 = [0, 1, 3, 2];                            // 00 01 11 10
const GRAY2_LABELS = ['00', '01', '11', '10'];

export function KmapView({
  nvars, headers, rows, omega,
}: {
  nvars: number;
  headers: string[];
  rows: Row[];
  omega: Record<string, boolean>;
}) {
  if (nvars < 1) {
    return <p className="muted">Karnaugh map needs at least 1 variable.</p>;
  }
  if (nvars > 6) {
    return <p className="muted">Karnaugh map not shown for n &gt; 6 (unreadable).</p>;
  }

  const omegaBits = headers.map(h => !!omega[h]);
  const bitsToIndex = (bits: boolean[]) => bits.reduce((a, b) => (a << 1) | (b ? 1 : 0), 0);
  const omegaIdx = bitsToIndex(omegaBits);

  const byIdx = new Map<number, Row>();
  for (const r of rows) byIdx.set(bitsToIndex(r.values), r);

  // Which bits belong to row axis, column axis, and (for 5-6) outer axes.
  // nvars=2: rowBits=[0], colBits=[1]
  // nvars=3: rowBits=[0], colBits=[1,2]  → 2 rows × 4 cols
  // nvars=4: rowBits=[0,1], colBits=[2,3] → 4 rows × 4 cols
  // nvars=5: like 4, but TWO maps side by side (outer: var 4)
  // nvars=6: like 4, but a 2x2 grid of maps (outer: vars 4,5)
  const panels: Array<{ title?: string; outerBits: boolean[] }> = [];
  if (nvars <= 4) {
    panels.push({ outerBits: [] });
  } else if (nvars === 5) {
    panels.push({ title: `${headers[4]} = 0`, outerBits: [false] });
    panels.push({ title: `${headers[4]} = 1`, outerBits: [true] });
  } else {
    for (const a of [false, true]) {
      for (const b of [false, true]) {
        panels.push({
          title: `${headers[4]} = ${a ? 1 : 0}, ${headers[5]} = ${b ? 1 : 0}`,
          outerBits: [a, b],
        });
      }
    }
  }

  return (
    <div>
      <Legend />
      <div style={{
        display: 'grid',
        gridTemplateColumns: panels.length === 4 ? '1fr 1fr' : 'auto',
        gap: 20,
        marginTop: 12,
      }}>
        {panels.map((p, i) => (
          <KmapPanel
            key={i}
            nvarsInPanel={Math.min(nvars, 4)}
            headers={headers}
            byIdx={byIdx}
            outerBits={p.outerBits}
            omegaIdx={omegaIdx}
            omegaBits={omegaBits}
            title={p.title}
          />
        ))}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------- panel

function KmapPanel({
  nvarsInPanel, headers, byIdx, outerBits, omegaIdx, omegaBits, title,
}: {
  nvarsInPanel: number;
  headers: string[];
  byIdx: Map<number, Row>;
  outerBits: boolean[];
  omegaIdx: number;
  omegaBits: boolean[];
  title?: string;
}) {
  // Row/column axis configuration for 2 / 3 / 4 inner variables.
  const spec = inner(nvarsInPanel, headers);
  const nRows = spec.rowCombos.length;
  const nCols = spec.colCombos.length;

  // Build the row-index key for a cell (globally in the truth table).
  // Order of bits in the index: variables as given in `headers` (MSB first).
  const cellIndex = (ri: number, ci: number): number => {
    const rowBits = spec.rowCombos[ri];      // values at spec.rowVars
    const colBits = spec.colCombos[ci];      // values at spec.colVars
    const nvarsTotal = headers.length;
    const bits = new Array<boolean>(nvarsTotal).fill(false);
    spec.rowVars.forEach((vIdx, k) => { bits[vIdx] = rowBits[k]; });
    spec.colVars.forEach((vIdx, k) => { bits[vIdx] = colBits[k]; });
    // outer: variables 4.. in header order
    outerBits.forEach((b, k) => { bits[4 + k] = b; });
    return bits.reduce((a, b) => (a << 1) | (b ? 1 : 0), 0);
  };

  const cellBits = (ri: number, ci: number): boolean[] => {
    const rowBits = spec.rowCombos[ri];
    const colBits = spec.colCombos[ci];
    const bits = new Array<boolean>(headers.length).fill(false);
    spec.rowVars.forEach((vIdx, k) => { bits[vIdx] = rowBits[k]; });
    spec.colVars.forEach((vIdx, k) => { bits[vIdx] = colBits[k]; });
    outerBits.forEach((b, k) => { bits[4 + k] = b; });
    return bits;
  };

  const CELL = 48;
  const H_LABEL = 24;
  const V_LABEL = 44;

  return (
    <div>
      {title && <div className="muted" style={{ fontSize: 13, marginBottom: 6 }}>{title}</div>}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `${V_LABEL}px repeat(${nCols}, ${CELL}px)`,
        gridTemplateRows: `${H_LABEL}px repeat(${nRows}, ${CELL}px)`,
        rowGap: 0, columnGap: 0,
      }}>
        {/* corner */}
        <div style={{
          display: 'flex', alignItems: 'end', justifyContent: 'center',
          fontSize: 11, color: 'var(--muted)',
        }}>
          <div style={{ textAlign: 'center', lineHeight: 1.1 }}>
            <div>{spec.colLabel}</div>
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 2 }}>{spec.rowLabel}</div>
          </div>
        </div>

        {/* column headers */}
        {spec.colCombos.map((_, ci) => (
          <div key={`c${ci}`} style={{
            display: 'flex', alignItems: 'end', justifyContent: 'center',
            fontSize: 12, color: 'var(--muted)', fontFamily: 'ui-monospace, monospace',
            paddingBottom: 4,
          }}>
            {spec.colLabels[ci]}
          </div>
        ))}

        {/* body: one row at a time */}
        {spec.rowCombos.map((_, ri) => (
          <Fragment key={ri}>
            <div key={`r${ri}`} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'end',
              fontSize: 12, color: 'var(--muted)', fontFamily: 'ui-monospace, monospace',
              paddingRight: 6,
            }}>
              {spec.rowLabels[ri]}
            </div>
            {spec.colCombos.map((_, ci) => {
              const idx = cellIndex(ri, ci);
              const r = byIdx.get(idx);
              const isOmega = idx === omegaIdx;
              const bits = cellBits(ri, ci);
              return (
                <Cell
                  key={`r${ri}c${ci}`}
                  row={r}
                  isOmega={isOmega}
                  bits={bits}
                  headers={headers}
                />
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------- cell

function Cell({
  row, isOmega, bits, headers,
}: {
  row: Row | undefined;
  isOmega: boolean;
  bits: boolean[];
  headers: string[];
}) {
  const old = !!row?.old;
  const neu = !!row?.new;
  const added = !old && neu;
  const removed = old && !neu;

  const bg =
    added   ? 'var(--kmap-added)'
    : removed ? 'var(--kmap-removed)'
    : old   ? 'var(--kmap-old)'
    : 'var(--panel)';

  const fg = (added || old || removed) ? 'var(--kmap-fg)' : 'var(--muted)';

  const tooltip = headers.map((h, i) => `${h}=${bits[i] ? 1 : 0}`).join(' ')
    + ` | Δ=${old ? 1 : 0} → Δ'=${neu ? 1 : 0}`;

  return (
    <div
      title={tooltip}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: bg,
        color: fg,
        border: '1px solid var(--border)',
        outline: isOmega ? '2px solid var(--danger)' : 'none',
        outlineOffset: isOmega ? -2 : 0,
        fontFamily: 'ui-monospace, monospace',
        fontSize: 16,
        fontWeight: added ? 700 : 500,
        position: 'relative',
      }}
    >
      {neu ? '1' : '0'}
      {added && (
        <span style={{
          position: 'absolute', top: 2, right: 4,
          fontSize: 10, color: 'var(--kmap-fg)', opacity: 0.6,
        }}>+</span>
      )}
      {isOmega && (
        <span style={{
          position: 'absolute', bottom: 2, left: 4,
          fontSize: 10, color: 'var(--danger)', fontWeight: 700,
        }}>ω</span>
      )}
    </div>
  );
}

// -------------------------------------------------------------------- legend

function Legend() {
  const box = (bg: string, label: string, extra?: React.CSSProperties) => (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginRight: 14 }}>
      <span style={{
        width: 16, height: 16, background: bg, border: '1px solid var(--border)',
        display: 'inline-block', ...extra,
      }} />
      <span style={{ fontSize: 12, color: 'var(--muted)' }}>{label}</span>
    </span>
  );
  return (
    <div style={{ marginBottom: 4 }}>
      {box('var(--panel)', 'rejected')}
      {box('var(--kmap-old)', 'accepted by Δ')}
      {box('var(--kmap-added)', 'added by revision')}
      {box('var(--panel)', 'ω', { outline: '2px solid var(--danger)', outlineOffset: -2 })}
    </div>
  );
}

// --------------------------------------------------------------- inner spec

function inner(n: number, headers: string[]): {
  rowVars: number[]; colVars: number[];
  rowCombos: boolean[][]; colCombos: boolean[][];
  rowLabels: string[]; colLabels: string[];
  rowLabel: string; colLabel: string;
} {
  // "n" here is the number of INNER variables for one panel (<=4).
  if (n === 1) {
    return { rowVars: [], colVars: [0], rowCombos: [[]], colCombos: [[false], [true]],
      rowLabels: ['·'], colLabels: ['0', '1'], rowLabel: '·', colLabel: headers[0] };
  }
  if (n === 2) {
    return {
      rowVars: [0], colVars: [1],
      rowCombos: [[false], [true]],
      colCombos: [[false], [true]],
      rowLabels: ['0', '1'],
      colLabels: ['0', '1'],
      rowLabel: headers[0], colLabel: headers[1],
    };
  }
  if (n === 3) {
    // rows: var 0;  cols: vars 1,2 (Gray)
    return {
      rowVars: [0], colVars: [1, 2],
      rowCombos: [[false], [true]],
      colCombos: GRAY2.map(g => [((g >> 1) & 1) === 1, (g & 1) === 1]),
      rowLabels: ['0', '1'],
      colLabels: GRAY2_LABELS,
      rowLabel: headers[0], colLabel: `${headers[1]}${headers[2]}`,
    };
  }
  // n == 4
  return {
    rowVars: [0, 1], colVars: [2, 3],
    rowCombos: GRAY2.map(g => [((g >> 1) & 1) === 1, (g & 1) === 1]),
    colCombos: GRAY2.map(g => [((g >> 1) & 1) === 1, (g & 1) === 1]),
    rowLabels: GRAY2_LABELS,
    colLabels: GRAY2_LABELS,
    rowLabel: `${headers[0]}${headers[1]}`,
    colLabel: `${headers[2]}${headers[3]}`,
  };
}

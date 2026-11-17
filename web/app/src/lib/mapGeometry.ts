// Exact PI fragments in Gray-code coordinates, including groups that cross map edges or panels.
import { mapPanels } from './feedback';

export interface VisualReason { id: string; states: number[]; text: string }
export interface MapVisualization { nvars: number; vars: string[]; accepted: boolean[]; reasons: VisualReason[]; reason_count: number | null; available: boolean }
export interface ReasonRectangle { row: number; column: number; rows: number; columns: number; wrap: boolean }

function runs(selected: boolean[]): { start: number; length: number }[] {
  const result: { start: number; length: number }[] = [];
  selected.forEach((value, index) => {
    if (!value) return;
    const last = result[result.length - 1];
    if (last && last.start + last.length === index) last.length++;
    else result.push({ start: index, length: 1 });
  });
  return result;
}

export function reasonRectangles(n: number, panelIndex: number, states: number[]): ReasonRectangle[] {
  if (states.length !== n || states.some(v => ![-1, 0, 1].includes(v))) throw new Error('A PI overlay needs one ternary state per variable.');
  const panel = mapPanels(n)[panelIndex], inner = Math.min(n, 4);
  if (!panel) throw new Error('Map panel is outside the variable universe.');
  if (panel.outer.some((value, i) => states[inner + i] !== 0 && value !== (states[inner + i] === 1))) return [];
  const matches = (value: number, count: number, start: number) => Array.from({ length: count }, (_, i) => states[start + i] === 0 || !!(value & (1 << (count - i - 1))) === (states[start + i] === 1)).every(Boolean);
  const selectedRows = panel.rows.map(row => matches(row, panel.rowBits, 0));
  const selectedColumns = panel.columns.map(col => matches(col, panel.colBits, panel.rowBits));
  const rowRuns = runs(selectedRows), columnRuns = runs(selectedColumns);
  const wrap = rowRuns.length > 1 || columnRuns.length > 1;
  return rowRuns.flatMap(row => columnRuns.map(column => ({ row: row.start, rows: row.length, column: column.start, columns: column.length, wrap })));
}

export function reasonColor(index: number): string {
  return `hsl(${(index * 137.508 + 14) % 360} 76% 53%)`;
}

export function reasonColorIndex(states: number[]): number {
  return states.reduce((code, value) => code * 3 + value + 1, 0);
}

// Thin wrapper over the FastAPI backend. All requests hit /api/* and are proxied to :8000 by Vite in dev.
import { MapVisualization } from './mapGeometry';

export type Clauses = number[][];

export interface Classifier {
  nvars: number;
  var_names: string[];
  clauses: Clauses;
}

export interface Example extends Classifier {
  id: string;
  label: string;
  mode: 'formula' | 'cnf' | 'truth';
  text: string;
  omega_hint: Record<string, boolean>;
  description?: string;
  positive_hint?: boolean[][];
  negative_hint?: boolean[][];
  budgets?: { epsilon: string; gamma: string };
}

export interface TraceStep {
  name: string;
  description: string;
  data: any;
}

export interface Trace {
  algorithm: string;
  steps: TraceStep[];
  sdd_dot: string;
  reasons?: Array<Record<string, boolean>>;
  nvars: number;
  var_names: string[];
  clauses: Clauses;
  original_visual?: MapVisualization;
}

async function request<T>(url: string, method = 'GET', body?: unknown): Promise<T> {
  const res = await fetch(url, { method, headers: body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    const raw = await res.text();
    let detail = raw;
    try { const data = JSON.parse(raw); detail = Array.isArray(data.detail) ? data.detail.map((v: any) => `${v.loc?.slice(1).join('.')}: ${v.msg}`).join('\n') : data.detail || raw; } catch { /* Preserve non-JSON server errors. */ }
    throw new Error(detail || res.statusText);
  }
  return res.json();
}
const post = <T,>(url: string, body: unknown) => request<T>(url, 'POST', body);

export type BatchAlgorithm = 'auto' | 'ord' | 'negative' | 'berd';
export interface BatchChoice {
  id: number; cost: number | null; loss: number; gain: number; accepted_count: number;
  equivalent_to: number | null; identity: boolean; source_free: boolean;
  edits: { source: string; descendants: string[]; cost: number }[];
  visualization: MapVisualization;
}
export interface ChoicePage { choices: BatchChoice[]; next_offset: number; has_more: boolean; total_plans: string | null; enumeration_complete: boolean }
export interface BatchExecutionTrace {
  events: { id: number; kind: string; title: string; summary: string; rows: Record<string, string | number>[];
    frames: { title: string; visualization: MapVisualization }[]; excess: number | null; candidate: number }[];
  total_events: number; omitted_events: number; limit: number; complete: boolean;
}
export interface BatchResult {
  algorithm: string; minimum_cost: number | null; solve_status: string; total_plans: string | null; source_count: string;
  original_count: number; old_positive: number; old_negative: number; loss_limit: number; gain_limit: number;
  epsilon: string; gamma: string; statistics: Record<string, unknown> | null; original_dot: string; page: ChoicePage;
  steps: { title: string; summary: string; details: string[]; rows: Record<string, string | number>[] }[];
  original_visual: MapVisualization;
  trace: BatchExecutionTrace;
}
export interface BatchJob { id: string; status: string; phase: string; elapsed_s: number; error?: string; result?: BatchResult }
export interface BatchPreview {
  choice: BatchChoice; truth_table: { headers: string[]; rows: { values: boolean[]; old: boolean; new: boolean; feedback: string | null }[] };
  original_dnf_latex: string; revised_dnf_latex: string; revised_cnf_latex: string; revised_dot: string;
  old_count: number; new_count: number; added_count: number; removed_count: number; positive_success: boolean; negative_success: boolean;
  visualization: MapVisualization;
}

export const api = {
  parse: (mode: string, text: string) =>
    post<Classifier>('/api/parse', { mode, text }),
  random: (nvars: number, density: number, seed?: number) =>
    post<Classifier>('/api/random', { nvars, density, seed }),
  examples: async (framework = 'unary') => (await request<{ examples: Example[] }>(framework === 'batch' ? '/api/batch/examples' : '/api/examples')).examples,
  fromTable: (var_names: string[], accepting: string[]) => post<Classifier>('/api/classifier/from-table', { var_names, accepting }),
  visualization: (body: Classifier) => post<MapVisualization>('/api/classifier/visualization', body),
  startBatch: (body: Classifier & { positive: boolean[][]; negative: boolean[][]; epsilon: string; gamma: string; algorithm: BatchAlgorithm; timeout_s: number }) => post<BatchJob>('/api/batch/jobs', body),
  batchStatus: (id: string) => request<BatchJob>(`/api/batch/jobs/${id}`),
  cancelBatch: (id: string) => request<BatchJob>(`/api/batch/jobs/${id}`, 'DELETE'),
  batchChoices: (id: string, offset: number) => request<ChoicePage>(`/api/batch/jobs/${id}/choices?offset=${offset}`),
  batchPreview: (id: string, choice: number) => request<BatchPreview>(`/api/batch/jobs/${id}/choices/${choice}`),
  revise: (alg: string, req: Classifier & { omega: Record<string, boolean> }) =>
    post<Trace>(`/api/revise/${alg}`, req),
  apply: (req: Classifier & { omega: Record<string, boolean>; reason: Record<string, boolean> }) =>
    post<{
      weakened_reason: Record<number, boolean>;
      accepts_omega: boolean;
      revised_dot: string;
      revised_size: number;
    }>('/api/apply', req),
};

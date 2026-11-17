// Exact feedback parsing, budget arithmetic and shared Gray-code mapping for both frameworks.
export type FeedbackSets = { positive: boolean[][]; negative: boolean[][] };
export const bitsKey = (values: boolean[]) => values.map(v => v ? '1' : '0').join('');
export const indexBits = (index: number, n: number) => Array.from({ length: n }, (_, i) => !!(index & (1 << (n - i - 1))));

function booleanValue(value: unknown): boolean {
  if (value === true || value === 1 || value === '1' || value === 'true') return true;
  if (value === false || value === 0 || value === '0' || value === 'false') return false;
  throw new Error(`Use 0/1 or true/false, not ${String(value)}.`);
}

function point(value: unknown, vars: string[]): boolean[] {
  if (typeof value === 'string' && /^[01]+$/.test(value)) value = value.split('');
  if (Array.isArray(value)) {
    if (value.length !== vars.length) throw new Error(`Each instance needs ${vars.length} values, in order ${vars.join(', ')}.`);
    return value.map(booleanValue);
  }
  if (value && typeof value === 'object') {
    const named = value as Record<string, unknown>;
    if (Object.keys(named).length !== vars.length || vars.some(v => !(v in named))) throw new Error(`A named instance must contain exactly: ${vars.join(', ')}.`);
    return vars.map(v => booleanValue(named[v]));
  }
  throw new Error('Enter complete assignments as bitstrings, arrays, or objects keyed by variable name.');
}

export function parseInstances(text: string, vars: string[]): boolean[][] {
  if (text.length > 200_000) throw new Error('Use a smaller feedback file for the interactive interface.');
  const source = text.trim();
  if (!source) return [];
  let values: boolean[][];
  if (source.startsWith('[') || source.startsWith('{')) {
    let parsed: unknown;
    try { parsed = JSON.parse(source); } catch { throw new Error('The feedback JSON is not valid.'); }
    if (Array.isArray(parsed)) {
      values = parsed.length === 0 ? [] : typeof parsed[0] === 'boolean' || typeof parsed[0] === 'number' ? [point(parsed, vars)] : parsed.map(v => point(v, vars));
    } else values = [point(parsed, vars)];
  } else {
    const lines = source.split(/\r?\n/).map(v => v.trim()).filter(v => v && !v.startsWith('#'));
    const header = lines[0]?.split(/[,\s;]+/);
    const hasHeader = header?.length === vars.length && new Set(header).size === vars.length && vars.every(v => header.includes(v));
    const order = hasHeader ? vars.map(v => header.indexOf(v)) : vars.map((_, i) => i);
    values = lines.slice(hasHeader ? 1 : 0).map((line, i) => {
      try {
        if (line.includes('=')) {
          const named: Record<string, string> = {};
          for (const pair of line.split(/[,\s;]+/)) {
            const [name, value, extra] = pair.split('=');
            if (!name || value === undefined || extra !== undefined || name in named) throw new Error('Use each variable once, for example a=0 b=1.');
            named[name] = value.toLowerCase();
          }
          return point(named, vars);
        }
        const tokens = /^[01]+$/.test(line) ? line.split('') : line.toLowerCase().split(/[,\s;]+/);
        if (tokens.length !== vars.length) return point(tokens, vars);
        return point(order.map(j => tokens[j]), vars);
      } catch (error) { throw new Error(`Line ${i + 1}: ${(error as Error).message}`); }
    });
  }
  return [...new Map(values.map(v => [bitsKey(v), v])).values()];
}

export function validateFeedback(feedback: FeedbackSets): FeedbackSets {
  const positives = new Set(feedback.positive.map(bitsKey));
  const conflict = feedback.negative.find(v => positives.has(bitsKey(v)));
  if (conflict) throw new Error(`${bitsKey(conflict)} is both positive and negative. Choose one target for that instance.`);
  return { positive: [...new Map(feedback.positive.map(v => [bitsKey(v), v])).values()], negative: [...new Map(feedback.negative.map(v => [bitsKey(v), v])).values()] };
}

export function parseFeedbackFile(text: string, vars: string[]): FeedbackSets {
  const source = text.trim();
  if (source.startsWith('{')) {
    let data: { positive?: unknown; negative?: unknown };
    try { data = JSON.parse(source); } catch { throw new Error('The feedback JSON is not valid.'); }
    if (!('positive' in data) && !('negative' in data)) throw new Error('A feedback file needs positive and/or negative arrays.');
    return validateFeedback({ positive: parseInstances(JSON.stringify(data.positive ?? []), vars), negative: parseInstances(JSON.stringify(data.negative ?? []), vars) });
  }
  const lines = source.split(/\r?\n/).map(v => v.trim()).filter(Boolean);
  const header = lines.shift()?.split(/[,\s;]+/);
  if (!header || header.length !== vars.length + 1) throw new Error(`CSV needs a header such as ${vars.join(',')},label.`);
  const labelIndex = header.findIndex(v => !vars.includes(v) && ['label', 'target', 'feedback'].includes(v.toLowerCase()));
  const columns = vars.map(v => header.indexOf(v));
  if (labelIndex < 0 || columns.some(v => v < 0) || new Set(header).size !== header.length) throw new Error('CSV headers must name every variable once and include label, target, or feedback.');
  const result: FeedbackSets = { positive: [], negative: [] };
  lines.forEach((line, i) => {
    const tokens = line.toLowerCase().split(/[,\s;]+/);
    if (tokens.length !== header.length) throw new Error(`CSV row ${i + 2} has the wrong number of columns.`);
    const label = tokens[labelIndex];
    const target = ['positive', 'p', '+', '1', 'true'].includes(label) ? 'positive' : ['negative', 'n', '-', '0', 'false'].includes(label) ? 'negative' : null;
    if (!target) throw new Error(`CSV row ${i + 2}: use positive/negative or 1/0 for the target.`);
    result[target].push(point(columns.map(j => tokens[j]), vars));
  });
  return validateFeedback(result);
}

export function parseBudget(value: string): { numerator: bigint; denominator: bigint } {
  const text = value.trim();
  if (text.length > 128 || !/^(?:\d+(?:\.\d*)?|\.\d+)(?:\/\d+)?$/.test(text)) throw new Error('Use a fraction or decimal between 0 and 1, such as 0, 1/3, 0.5, or 1.');
  const [decimal, divisor = '1'] = text.split('/');
  if (text.includes('/') && decimal.includes('.')) throw new Error('Use integers in a fraction, such as 1/2, or enter a decimal without a slash.');
  const [whole = '0', fractional = ''] = decimal.split('.');
  const numerator = BigInt((whole || '0') + fractional);
  const denominator = 10n ** BigInt(fractional.length) * BigInt(divisor);
  if (denominator === 0n || numerator > denominator) throw new Error('The bound must be between 0 and 1.');
  return { numerator, denominator };
}

export function budgetLimit(value: string, denominatorCount: number): number {
  const rational = parseBudget(value);
  return Number(BigInt(denominatorCount) * rational.numerator / rational.denominator);
}

export function algorithmEligibility(algorithm: string, positiveCount: number, negativeCount: number, epsilon: string, gamma: string): string | null {
  const loss = parseBudget(epsilon), gain = parseBudget(gamma);
  if (algorithm === 'ord' && (negativeCount > 0 || gain.numerator !== gain.denominator)) return 'ORD needs no negative feedback and unrestricted extra gain (γ = 1).';
  if (algorithm === 'negative' && (positiveCount > 0 || loss.numerator !== loss.denominator)) return 'The independent negative solver needs no positive feedback and unrestricted extra loss (ε = 1).';
  return null;
}

export function classifierAccepts(clauses: number[][], values: boolean[]): boolean {
  return clauses.every(clause => clause.some(lit => values[Math.abs(lit) - 1] === (lit > 0)));
}

export function mapPanels(n: number): { outer: boolean[]; rowBits: number; colBits: number; rows: number[]; columns: number[]; indices: number[][] }[] {
  if (n < 1 || n > 6) throw new Error('Interactive Karnaugh maps support 1 to 6 variables.');
  const inner = Math.min(n, 4), rowBits = Math.floor(inner / 2), colBits = inner - rowBits;
  const gray = (count: number) => Array.from({ length: 1 << count }, (_, i) => i ^ (i >> 1));
  const rows = gray(rowBits), columns = gray(colBits);
  return Array.from({ length: 1 << (n - inner) }, (_, panel) => ({
    outer: indexBits(panel, n - inner), rowBits, colBits, rows, columns,
    indices: rows.map(row => columns.map(col => ((row << colBits) | col) * (1 << (n - inner)) + panel)),
  }));
}

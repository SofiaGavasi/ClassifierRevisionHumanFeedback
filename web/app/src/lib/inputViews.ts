// Lossless classifier representations for shared editor tabs, including constants and unused variables.
import { Classifier } from './api';
import { classifierAccepts, indexBits } from './feedback';

export function tableClassifier(vars: string[], accepted: boolean[]): Classifier {
  if (vars.length < 1 || vars.length > 8 || accepted.length !== 2 ** vars.length) throw new Error('Use a complete truth table for 1 to 8 variables.');
  if (new Set(vars).size !== vars.length || vars.some(v => !/^[A-Za-z_][A-Za-z0-9_]*$/.test(v))) throw new Error('Use different valid names for every variable.');
  return { nvars: vars.length, var_names: [...vars], clauses: accepted.flatMap((yes, index) => yes ? [] : [indexBits(index, vars.length).map((value, i) => value ? -i - 1 : i + 1)]) };
}

export function classifierViews(classifier: Classifier) {
  const names = classifier.var_names;
  const literal = (value: number) => `${value < 0 ? '~' : ''}${names[Math.abs(value) - 1]}`;
  const accepted = classifier.nvars <= 8 ? Array.from({ length: 2 ** classifier.nvars }, (_, i) => classifierAccepts(classifier.clauses, indexBits(i, classifier.nvars))) : [];
  const contradiction = classifier.clauses.some(clause => !clause.length) || accepted.length > 0 && accepted.every(v => !v);
  const tautology = !classifier.clauses.length || accepted.length > 0 && accepted.every(Boolean);
  const formula = contradiction ? 'False' : tautology ? 'True' : classifier.clauses.map(clause => `(${clause.map(literal).join(' | ')})`).join(' & ');
  const cnf = contradiction ? `${names[0]}\n~${names[0]}` : tautology ? '# True: no clauses' : classifier.clauses.map(clause => clause.map(literal).join(' ')).join('\n');
  return { formula, cnf, accepted };
}

export function emptyInput(): Classifier {
  return tableClassifier(['a', 'b', 'c'], Array(8).fill(false));
}

// Pure UI input and Gray-map tests using the existing TypeScript compiler and Node test runner.
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/feedback.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ES2020 } });
const f = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputText).toString('base64')}`);
const vars = ['a', 'b', 'c'];

test('complete feedback accepts bitstrings, arrays, named JSON and named text', () => {
  const expected = [[false, false, true], [true, false, true]];
  for (const text of ['001\n101\n001', '[[0,0,1],[1,0,1]]', '["001","101"]', '[{"c":1,"b":0,"a":0},{"a":1,"b":0,"c":1}]', 'a=0 b=0 c=1\na=1 b=0 c=1', 'c,a,b\n1,0,0\n1,1,0']) assert.deepEqual(f.parseInstances(text, vars), expected);
  assert.deepEqual(f.parseInstances('[false,true,false]', vars), [[false,true,false]]);
  assert.deepEqual(f.parseInstances('# comment only', vars), []);
});

test('feedback rejects partial, non-Boolean, malformed and contradictory inputs', () => {
  for (const text of ['01', '0,1,2', '{"a":1}', '{"a":1,"b":0,"z":1}', '[[0,1,0]', 'a=0 a=1 c=0']) assert.throws(() => f.parseInstances(text, vars));
  assert.throws(() => f.validateFeedback({ positive: [[false]], negative: [[false]] }), /both positive and negative/);
});

test('JSON and reordered labelled CSV import preserve targets and reject ambiguity', () => {
  const expected = { positive: [[false,false,true]], negative: [[true,false,true]] };
  assert.deepEqual(f.parseFeedbackFile('{"positive":["001"],"negative":[[1,0,1]]}', vars), expected);
  assert.deepEqual(f.parseFeedbackFile('label,c,b,a\npositive,1,0,0\nnegative,1,0,1', vars), expected);
  assert.throws(() => f.parseFeedbackFile('a,b,c,label\n0,0,1,perhaps', vars));
  assert.throws(() => f.parseFeedbackFile('{"positive":["001"],"negative":["001"]}', vars));
  assert.deepEqual(f.parseFeedbackFile('label,a,target\n0,1,positive', ['label','a']), {positive:[[false,true]],negative:[]});
});

test('semantic thresholds use exact fractions and reject invalid bounds', () => {
  assert.equal(f.budgetLimit('1/3', 6), 2);
  assert.equal(f.budgetLimit('0.1', 30), 3);
  assert.equal(f.budgetLimit('.5', 3), 1);
  assert.equal(f.budgetLimit('0', 11), 0);
  assert.equal(f.budgetLimit('1', 11), 11);
  for (const value of ['-1', '1.1', '1/0', 'a', '', '1/2/3', '0.5/2']) assert.throws(() => f.parseBudget(value));
});

test('algorithm restrictions match the exact dispatcher preconditions', () => {
  assert.equal(f.algorithmEligibility('ord', 2, 0, '0', '1'), null);
  assert.match(f.algorithmEligibility('ord', 2, 1, '0', '1'), /ORD/);
  assert.match(f.algorithmEligibility('ord', 2, 0, '0', '1/2'), /ORD/);
  assert.equal(f.algorithmEligibility('negative', 0, 2, '1', '0'), null);
  assert.match(f.algorithmEligibility('negative', 1, 2, '1', '0'), /negative solver/);
  assert.equal(f.algorithmEligibility('berd', 2, 2, '0', '0'), null);
});

test('every map from one to six variables visits every assignment exactly once in Gray order', () => {
  for (let n = 1; n <= 6; n++) {
    const panels = f.mapPanels(n), indices = panels.flatMap(p => p.indices.flat());
    assert.equal(indices.length, 2 ** n);
    assert.deepEqual([...indices].sort((a,b) => a-b), Array.from({length: 2 ** n}, (_, i) => i));
    for (const panel of panels) for (const axis of [panel.rows, panel.columns]) {
      for (let i = 0; i < axis.length && axis.length > 1; i++) {
        const difference = axis[i] ^ axis[(i + 1) % axis.length];
        assert.equal(difference & (difference-1), 0);
      }
    }
    for (const index of indices) assert.equal(parseInt(f.bitsKey(f.indexBits(index, n)), 2), index);
  }
  assert.throws(() => f.mapPanels(7));
});

test('client CNF shading handles tautology, contradiction and negative literals', () => {
  assert.equal(f.classifierAccepts([], [false]), true);
  assert.equal(f.classifierAccepts([[]], [true]), false);
  assert.equal(f.classifierAccepts([[1,-2]], [false,false]), true);
  assert.equal(f.classifierAccepts([[1,-2]], [false,true]), false);
});

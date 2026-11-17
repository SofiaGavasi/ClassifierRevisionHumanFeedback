// Exhaustive ternary-cube geometry and lossless shared-input representations, using independent cell checks.
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

async function moduleSource(name, imports = {}) {
  const source = await readFile(new URL(`../src/lib/${name}.ts`, import.meta.url), 'utf8');
  let code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ES2020 } }).outputText;
  for (const [path, url] of Object.entries(imports)) code = code.replaceAll(`'${path}'`, `'${url}'`).replaceAll(`"${path}"`, `'${url}'`);
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`;
}
const feedbackUrl = await moduleSource('feedback');
const f = await import(feedbackUrl);
const geometry = await import(await moduleSource('mapGeometry', { './feedback': feedbackUrl }));
const input = await import(await moduleSource('inputViews', { './feedback': feedbackUrl }));

test('every PI outline covers exactly its ternary cube, across every Gray panel and wrap', () => {
  for (let n = 1; n <= 6; n++) {
    const panels = f.mapPanels(n);
    for (let code = 0; code < 3 ** n; code++) {
      let cursor = code;
      const states = Array.from({ length: n }, () => { const value = cursor % 3 - 1; cursor = Math.floor(cursor / 3); return value; });
      const outlined = new Set();
      panels.forEach((panel, pi) => {
        for (const rectangle of geometry.reasonRectangles(n, pi, states)) {
          for (let row = rectangle.row; row < rectangle.row + rectangle.rows; row++) for (let col = rectangle.column; col < rectangle.column + rectangle.columns; col++) {
            const index = panel.indices[row][col];
            assert.ok(!outlined.has(index), 'fragments for one PI must not duplicate cells');
            outlined.add(index);
          }
        }
      });
      const expected = new Set(Array.from({ length: 2 ** n }, (_, i) => i).filter(i => states.every((s, feature) => !s || !!(i & (1 << (n - feature - 1))) === (s === 1))));
      assert.deepEqual(outlined, expected, `n=${n}, states=${states}`);
    }
  }
});

test('a corner-wrapping PI uses four matching unfilled rectangle fragments', () => {
  const rectangles = geometry.reasonRectangles(4, 0, [0,-1,0,-1]);
  assert.equal(rectangles.length, 4);
  assert.ok(rectangles.every(r => r.wrap && r.rows === 1 && r.columns === 1));
  assert.throws(() => geometry.reasonRectangles(2, 0, [1]));
  assert.throws(() => geometry.reasonRectangles(2, 0, [2,0]));
});

test('PI colours remain distinct and deterministic throughout supported explicit cube families', () => {
  const colors = Array.from({ length: 729 }, (_, i) => geometry.reasonColor(i));
  assert.equal(new Set(colors).size, colors.length);
  assert.equal(geometry.reasonColor(17), colors[17]);
  const codes = new Set();
  for (let code = 0; code < 729; code++) { let value = code; const states = Array.from({length: 6}, () => { const state = value % 3 - 1; value = Math.floor(value / 3); return state; }); codes.add(geometry.reasonColorIndex(states)); }
  assert.equal(codes.size, 729);
});

test('table transport and every synchronized view retain exact constants, unused variables and truth', () => {
  for (let n = 1; n <= 6; n++) {
    const vars = Array.from({ length: n }, (_, i) => `feature_${i}`);
    for (const accepted of [Array(2 ** n).fill(false), Array(2 ** n).fill(true), Array.from({length: 2 ** n}, (_, i) => !!(i & (1 << (n - 1))))]) {
      const classifier = input.tableClassifier(vars, accepted), views = input.classifierViews(classifier);
      assert.equal(classifier.nvars, n);
      assert.deepEqual(classifier.var_names, vars);
      assert.deepEqual(views.accepted, accepted);
      assert.ok(views.formula.length && views.cnf.length);
      if (accepted.every(Boolean)) assert.equal(views.formula, 'True');
      if (accepted.every(v => !v)) assert.equal(views.formula, 'False');
    }
  }
  assert.throws(() => input.tableClassifier(['a','a'], [false,false,false,false]));
  assert.throws(() => input.tableClassifier(['a'], [true]));
});

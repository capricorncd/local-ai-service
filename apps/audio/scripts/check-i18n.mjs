import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';

const en = JSON.parse(fs.readFileSync('src/locales/en.json', 'utf8'));
const zh = JSON.parse(fs.readFileSync('src/locales/zh-CN.json', 'utf8'));
const ja = JSON.parse(fs.readFileSync('src/locales/ja.json', 'utf8'));
const placeholders = text => [...text.matchAll(/\{\d+\}/g)].map(m => m[0]).sort();
for (const [language, dictionary] of Object.entries({en, 'zh-CN':zh, ja})) {
  assert.deepEqual(Object.keys(dictionary).sort(), Object.keys(zh).sort(), `${language}: translation keys`);
  for (const [key, value] of Object.entries(dictionary)) {
    assert.ok(value.trim(), `${language}: empty translation: ${key}`);
    assert.deepEqual(placeholders(value), placeholders(key), `${language}: placeholder mismatch: ${key}`);
  }
}
for (const file of fs.readdirSync('src').filter(f => f.endsWith('.tsx'))) {
  const tree = ts.createSourceFile(file, fs.readFileSync(`src/${file}`, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  function visit(node) {
    if (ts.isCallExpression(node) && node.expression.getText(tree) === 't' && node.arguments[0] && ts.isStringLiteral(node.arguments[0])) {
      assert.ok(Object.hasOwn(en, node.arguments[0].text), `${file}: missing translation ${node.arguments[0].text}`);
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
}
console.log(`Checked ${Object.keys(en).length} entries in Chinese, English and Japanese, placeholders and UI translation keys.`);

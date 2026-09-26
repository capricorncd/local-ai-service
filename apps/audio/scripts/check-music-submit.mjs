import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import ts from 'typescript';

// Exercise the actual UI submission function without model inference.
const source = fs.readFileSync('src/main.tsx', 'utf8');
const start = source.indexOf('async function generateMusic()');
const end = source.indexOf('async function act(', start);
assert.ok(start >= 0 && end > start);
const code = ts.transpileModule(source.slice(start, end), {
  compilerOptions: {target: ts.ScriptTarget.ES2022},
}).outputText;
for (const reference of [null, {name: 'reference.mp4'}]) {
  const calls = [];
  const context = {
    musicWorkspace: 'Test workspace', musicReference: reference, variation: null, lora: {}, musicMinutes: '',
    songTitle: '', lyrics: '', style: '', count: 1, seed: 42, mode: 'full', generateScore: false,
    isTauri: () => true, uploadVoice: async () => 'reference-upload',
    api: async (path, options) => { calls.push({path, options}); return []; },
    setJobs: () => {}, notify: () => {}, t: text => text,
  };
  vm.createContext(context);
  vm.runInContext(code, context);
  await context.generateMusic();
  const request = calls[0];
  assert.equal(request.path, reference ? '/internal/music/reference' : '/v1/music/generate?wait=false');
  const body = JSON.parse(request.options.body);
  const music = reference ? body.music : body;
  assert.equal(music.workspace, 'Test workspace');
  assert.equal(music.style, '');
  assert.equal(music.lyrics, '');
  if (reference) assert.equal(body.upload_id, 'reference-upload');
}
console.log('UI submits blank style and lyrics with and without a reference.');

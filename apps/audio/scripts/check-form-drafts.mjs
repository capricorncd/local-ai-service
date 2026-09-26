import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import ts from 'typescript';

const values = new Map();
const code = ts.transpileModule(fs.readFileSync('src/useDraft.ts','utf8'), {
  compilerOptions: {target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS},
}).outputText;
let errorCount = 0;
const context = {
  exports: {}, Event,
  window: {dispatchEvent: () => errorCount++},
  localStorage: {getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v)},
  require: () => ({useState: initial=>[typeof initial==='function'?initial():initial,()=>{}],useRef:value=>({current:value}),useCallback:f=>f}),
};
vm.runInNewContext(code,context);
const {useDraft,readDraft}=context.exports;
const [,setLyrics]=useDraft('lyrics','');
setLyrics('春风\n[Chorus]');
assert.equal(useDraft('lyrics','')[0],'春风\n[Chorus]');
setLyrics('');
assert.equal(useDraft('lyrics','default')[0],'');
const [,setCount]=useDraft('count',1);
setCount(n=>n+1);setCount(n=>n+1);
assert.equal(useDraft('count',1)[0],3);
const [,setScore]=useDraft('score',true);setScore(false);
assert.equal(readDraft('score',true),false);
const [,setWorkspace]=useDraft('workspace','');setWorkspace(null);
assert.equal(readDraft('workspace',null),null);
assert.equal(readDraft('workspace','',v=>v===null||typeof v==='string'),null);
values.set('local-ai-draft-v1:page','"removed-page"');
assert.equal(readDraft('page','overview',v=>['overview','music'].includes(v)),'overview');
values.set('local-ai-draft-v1:lyrics','broken json');
assert.equal(readDraft('lyrics','fallback'),'fallback');
values.set('local-ai-draft-v1:count','"wrong type"');
assert.equal(readDraft('count',1),1);
context.localStorage.setItem=()=>{throw Error('Quota exceeded');};
setLyrics('unsaved');assert.equal(errorCount,1);
console.log('Draft restoration, empty values, updater ordering, invalid storage and quota failure checks passed.');

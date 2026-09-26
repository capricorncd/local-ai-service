import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';import ts from 'typescript';
const output=ts.transpileModule(readFileSync(new URL('../src/ShotDuration.tsx',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const m={};new Function('require','exports',output)(()=>({}),m);
assert.deepEqual(m.durationParts(5,24),{seconds:5,frames:0});assert.equal(m.composeDuration(2,12,24),2.5);assert.deepEqual(m.durationParts(2.5,24),{seconds:2,frames:12});assert.equal(m.composeDuration(0,1,24),1/24);assert.equal(m.composeDuration(0,0,24),1/24);assert.equal(m.composeDuration(3600,23,24),3600);
for(const fps of [1,24,25,30,60,120])for(const total of [1,23,24,79,3600*fps]){const parts=m.durationParts(total/fps,fps);assert(Math.abs(m.composeDuration(parts.seconds,parts.frames,fps)-total/fps)<1e-9);}
console.log('Shot duration: zero default frames, fractional seconds, frame rates, bounds and round trips passed');

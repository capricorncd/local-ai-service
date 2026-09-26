import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import ts from 'typescript';
const code=ts.transpileModule(fs.readFileSync('src/ReferenceMedia.tsx','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const slots=[];let cursor=0, online=false, pendingEffects=[], tree;
const react={
 useContext:()=>online,
 useState(initial){const i=cursor++;if(!(i in slots))slots[i]=initial;return [slots[i],value=>{slots[i]=typeof value==='function'?value(slots[i]):value;}];},
 useRef(initial){const i=cursor++;return slots[i]??(slots[i]={current:initial});},
 useEffect(fn,deps){const i=cursor++;const old=slots[i];if(!old||deps.some((d,n)=>!Object.is(d,old.deps[n]))){pendingEffects.push(()=>{old?.cleanup?.();slots[i]={deps,cleanup:fn()};});}}
};
const revoked=[];let objectUrls=0;
const runtime={jsx:(type,props)=>({type,props}),jsxs:(type,props)=>({type,props}),Fragment:'fragment'};
const context={exports:{},FormData,Blob,Uint8Array,atob,URL:{createObjectURL:()=>`blob:${++objectUrls}`,revokeObjectURL:url=>revoked.push(url)},require:name=>name==='react'?react:name==='react/jsx-runtime'?runtime:name==='./ApiReadyContext'?{ApiReadyContext:{}}:name==='./i18n'?{t:x=>x}: {}};
vm.runInNewContext(code,context);
let file=new File(['video'],'reference.mp4'), calls=[], fail=false, resolvePreview;
const api=async path=>{calls.push(path);if(path==='/v1/uploads')return {upload_id:'reference'};if(fail)throw Error('preview failed');if(resolvePreview==='defer')return new Promise(resolve=>resolvePreview=resolve);return {audio_base64:'UklGRg=='};};
function render(){cursor=0;tree=context.exports.ReferenceMedia({file,onChange:()=>{},api,service:'music'});const effects=pendingEffects;pendingEffects=[];effects.forEach(f=>f());}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;return [node.props?.children].flat(Infinity).map(child=>find(child,predicate)).find(Boolean);}
render();await flush();assert.equal(calls.length,0,'Restored video must wait for connection');
online=true;render();await flush();render();assert.equal(calls.length,2);assert.ok(find(tree,n=>n.type==='audio'));
render();await flush();assert.equal(calls.length,2,'Unrelated renders must not reload preview');
online=false;render();assert.equal(revoked.length,1);
fail=true;online=true;render();await flush();render();assert.ok(find(tree,n=>n.props?.role==='alert'));
const retry=find(tree,n=>n.type==='button'&&n.props?.children==='重试预览');assert.ok(retry);
fail=false;retry.props.onClick();render();await flush();render();assert.ok(find(tree,n=>n.type==='audio'));assert.ok(!find(tree,n=>n.props?.role==='alert'));
// A stale extraction result must not replace a newly selected local audio file.
resolvePreview='defer';file=new File(['video'],'other.mp4');render();await flush();const complete=resolvePreview;
online=false;file=new File(['audio'],'local.wav');render();await flush();render();const localUrl=find(tree,n=>n.type==='audio').props.src;
complete({audio_base64:'UklGRg=='});await flush();render();assert.equal(find(tree,n=>n.type==='audio').props.src,localUrl);
console.log('Reference preview checks passed: startup wait, auto reconnect, retry, stable renders, local audio offline, stale result cleanup.');

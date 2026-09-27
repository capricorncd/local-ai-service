import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';import {build} from 'esbuild';import {rm} from 'node:fs/promises';
const dom=new JSDOM('<div id="root"></div>',{pretendToBeVisual:true});
for(const key of ['window','document','navigator','HTMLElement','Event','KeyboardEvent'])Object.defineProperty(globalThis,key,{value:dom.window[key],configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const {default:React,act}=await import('react');const {createRoot}=await import('react-dom/client');
const out=new URL('./.input-tag-test.mjs',import.meta.url);
await build({entryPoints:['packages/ui/src/InputTag.tsx'],outfile:out.pathname.replace(/^\/([A-Za-z]:)/,'$1'),bundle:true,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'}});
try{
 const {InputTag}=await import(out.href);const root=createRoot(document.querySelector('#root'));let value=[],disabled=false,readOnly=false;
 const render=()=>root.render(React.createElement(InputTag,{value,disabled,readOnly,clearable:true,onChange:next=>{value=next;render();}}));
 await act(render);
 const type=async text=>act(()=>{const input=document.querySelector('input');Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype,'value').set.call(input,text);input.dispatchEvent(new Event('input',{bubbles:true}));});
 const enter=async(isComposing=false)=>act(()=>document.querySelector('input').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing,bubbles:true,cancelable:true})));
 await type(' 主角 ');await enter(true);assert.deepEqual(value,[]);await enter();assert.deepEqual(value,['主角']);
 await type('主角');await enter();assert.deepEqual(value,['主角']);
 await type('  ');await enter();assert.deepEqual(value,['主角']);
 await type('第一季');await enter();assert.deepEqual(value,['主角','第一季']);
 await act(()=>document.querySelector('[aria-label="删除标签：主角"]').click());assert.deepEqual(value,['第一季']);
 disabled=true;await act(render);assert(document.querySelector('input').disabled);assert(!document.querySelector('[aria-label="清空所有标签"]'));
 await act(()=>document.querySelector('[aria-label="删除标签：第一季"]').click());assert.deepEqual(value,['第一季']);
 disabled=false;readOnly=true;await act(render);assert(document.querySelector('input').readOnly);assert.equal(document.querySelectorAll('button').length,0);
 readOnly=false;await act(render);await act(()=>document.querySelector('[aria-label="清空所有标签"]').click());assert.deepEqual(value,[]);
 await act(()=>root.unmount());console.log('InputTag: add, IME, whitespace, duplicates, remove, disabled, readonly and clear passed');
}finally{await rm(out,{force:true});dom.window.close();}

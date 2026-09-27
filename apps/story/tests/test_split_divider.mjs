import assert from 'node:assert/strict';import {JSDOM} from 'jsdom';import {build} from 'esbuild';import {rm} from 'node:fs/promises';
const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost',pretendToBeVisual:true});
for(const key of ['window','document','navigator','HTMLElement','Event','KeyboardEvent','MouseEvent','localStorage'])Object.defineProperty(globalThis,key,{value:dom.window[key],configurable:true});
globalThis.getComputedStyle=dom.window.getComputedStyle.bind(dom.window);document.documentElement.style.fontSize='16px';globalThis.IS_REACT_ACT_ENVIRONMENT=true;
globalThis.ResizeObserver=class{observe(){}disconnect(){}};
dom.window.HTMLElement.prototype.getBoundingClientRect=function(){return this.getAttribute('role')==='separator'?{width:8,left:668,right:676}:{width:1000,left:0,right:1000};};
dom.window.HTMLElement.prototype.setPointerCapture=function(){};dom.window.HTMLElement.prototype.hasPointerCapture=()=>false;
const {default:React,act}=await import('react');const {createRoot}=await import('react-dom/client');
const out=new URL('./.split-divider-test.mjs',import.meta.url);
await build({entryPoints:['packages/ui/src/SplitDivider.tsx'],outfile:out.pathname.replace(/^\/([A-Za-z]:)/,'$1'),bundle:true,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'}});
try{const {SplitDivider}=await import(out.href);const root=createRoot(document.querySelector('#root'));const render=()=>root.render(React.createElement('div',null,React.createElement(SplitDivider,{storageKey:'test-split'})));await act(render);
const separator=document.querySelector('[role=separator]');const width=()=>parseFloat(separator.parentElement.style.getPropertyValue('--split-right'));
assert.equal(width(),20.25);
await act(()=>separator.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true})));assert.equal(width(),21.25);assert(localStorage.getItem('test-split'));
const pointer=async(type,x)=>act(()=>{const e=new MouseEvent(type,{bubbles:true,button:0,clientX:x});Object.defineProperty(e,'pointerId',{value:1});separator.dispatchEvent(e);});
await pointer('pointerdown',668);await pointer('pointermove',990);await pointer('pointerup',990);assert.equal(width(),16);
await pointer('pointerdown',668);await pointer('pointermove',0);await pointer('pointerup',0);assert.equal(width(),42);
await act(()=>separator.dispatchEvent(new MouseEvent('dblclick',{bubbles:true})));assert.equal(width(),20.25);assert.equal(localStorage.getItem('test-split'),null);
await act(()=>root.unmount());console.log('Split divider: keyboard, drag, bounds, persistence and reset passed');}finally{await rm(out,{force:true});dom.window.close();}

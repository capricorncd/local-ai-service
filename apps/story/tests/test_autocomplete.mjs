import assert from 'node:assert/strict';import{JSDOM}from'jsdom';import{build}from'esbuild';import{rm}from'node:fs/promises';
const dom=new JSDOM('<div id="root"></div>',{pretendToBeVisual:true});for(const k of ['window','document','navigator','HTMLElement','Event','KeyboardEvent'])Object.defineProperty(globalThis,k,{value:dom.window[k],configurable:true});globalThis.getComputedStyle=dom.window.getComputedStyle.bind(dom.window);globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const{default:React,act}=await import('react');const{createRoot}=await import('react-dom/client');const out=new URL('./.autocomplete-test.mjs',import.meta.url);await build({entryPoints:['packages/ui/src/Autocomplete.tsx'],outfile:out.pathname.replace(/^\/([A-Za-z]:)/,'$1'),bundle:true,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'}});
try{const{Autocomplete,AutocompleteSelect}=await import(out.href);const root=createRoot(document.querySelector('#root'));let value='旧的自定义内容';const writes=[];const render=()=>root.render(React.createElement(Autocomplete,{label:'运镜',value,options:['固定','轻推','缓慢推进'],onChange:v=>{value=v;writes.push(v);render();}}));await act(render);const input=document.querySelector('input');await act(()=>input.focus());assert.equal(document.querySelectorAll('[role=option]').length,3);assert.equal(writes.length,0);
const type=async text=>{await act(()=>{Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype,'value').set.call(input,text);input.dispatchEvent(new Event('input',{bubbles:true}));});};await type('推');assert.equal(document.querySelectorAll('[role=option]').length,2);await act(()=>input.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true})));await act(()=>input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true,cancelable:true})));assert.equal(value,'推');await act(()=>input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true})));assert.equal(value,'轻推');assert(!document.querySelector('[role=listbox]'));
await type('任意运镜说明');assert(document.querySelector('.ui-autocomplete-empty'));await act(()=>input.blur());assert.equal(value,'任意运镜说明');await act(()=>input.focus());await act(()=>document.querySelector('[role=option]').click());assert.equal(value,'固定');await type('');assert.equal(value,'');await act(()=>input.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true})));assert(!document.querySelector('[role=listbox]'));
// Fixed-choice mode displays labels but only saves actual option values.
let fixed='cuda'; const fixedWrites=[]; let locked=false;
const renderFixed=()=>root.render(React.createElement('label',null,'设备',React.createElement(AutocompleteSelect,{value:fixed,disabled:locked,onChange:e=>{fixed=e.target.value;fixedWrites.push(fixed);renderFixed();}},[
 React.createElement('option',{key:'cuda',value:'cuda'},'NVIDIA GPU'),
 React.createElement('option',{key:'blocked',value:'blocked',disabled:true},'不可用设备'),
 React.createElement('option',{key:'cpu',value:'cpu'},'CPU'),
 React.createElement('option',{key:'empty',value:''},'不加载'),
 React.createElement('option',{key:'number',value:2},2,' 首'),
 React.createElement('option',{key:'implicit'},'自动')
])));
await act(renderFixed);const fixedInput=document.querySelector('input');
const fixedType=async text=>act(()=>{Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype,'value').set.call(fixedInput,text);fixedInput.dispatchEvent(new Event('input',{bubbles:true}));});
const key=async key=>act(()=>fixedInput.dispatchEvent(new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true})));
assert.equal(fixedInput.value,'NVIDIA GPU');await act(()=>fixedInput.focus());await act(()=>document.querySelector('[role=option]').click());assert.equal(fixedWrites.length,0);await fixedType('无效值');assert.equal(fixed,'cuda');assert.equal(fixedWrites.length,0);assert(document.querySelector('.ui-autocomplete-empty'));await act(()=>fixedInput.blur());assert.equal(fixedInput.value,'NVIDIA GPU');
await act(()=>fixedInput.focus());await fixedType('cpu');await key('ArrowDown');await key('Enter');assert.equal(fixed,'cpu');assert.equal(fixedInput.value,'CPU');
await act(()=>fixedInput.click());assert(document.querySelector('[role=listbox]'));await act(()=>document.querySelector('[aria-disabled=true]').click());assert.equal(fixed,'cpu');
await key('ArrowDown');await key('ArrowDown');assert.equal(document.getElementById(fixedInput.getAttribute('aria-activedescendant')).textContent,'CPU');await key('Escape');
await act(()=>fixedInput.click());await fixedType('不加载');await key('Enter');assert.equal(fixed,'');assert.equal(fixedInput.value,'不加载');
await fixedType('首');await key('ArrowDown');await key('Enter');assert.equal(fixed,'2');assert.equal(fixedInput.value,'2 首');
await fixedType('自动');await key('Enter');assert.equal(fixed,'自动');
await fixedType('cpu');await key('Escape');assert.equal(fixed,'自动');assert.equal(fixedInput.value,'自动');
locked=true;await act(renderFixed);assert(fixedInput.disabled);assert(!document.querySelector('[role=listbox]'));
assert.equal(document.querySelectorAll('select').length,0);
await act(()=>root.unmount());console.log('Autocomplete: existing values, filtering, keyboard selection, IME, arbitrary input, click selection, clearing, fixed labels/values, invalid search, disabled options, numeric/empty values and label activation passed');}finally{await rm(out,{force:true});dom.window.close();}

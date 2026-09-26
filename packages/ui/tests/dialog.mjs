import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {build} from 'esbuild';
import {rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const dom=new JSDOM('<div id="root"></div>');
for(const key of ['window','document','navigator','HTMLElement','Event','KeyboardEvent'])Object.defineProperty(globalThis,key,{value:dom.window[key],configurable:true});
dom.window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
dom.window.HTMLDialogElement.prototype.close=function(){this.open=false;};
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const {default:React,act}=await import('react'),{createRoot}=await import('react-dom/client');
const out=new URL('./.dialog-test.mjs',import.meta.url);
await build({entryPoints:['packages/ui/src/Dialog.tsx'],outfile:fileURLToPath(out),bundle:true,format:'esm',platform:'node',packages:'external',jsx:'automatic',loader:{'.css':'empty'}});
try{
 const {Dialog,DialogActions,InfoTip}=await import(out.href);const root=createRoot(document.getElementById('root'));let saved=0,closed=0;
 await act(()=>root.render(React.createElement(Dialog,{title:'设置',onClose:()=>closed++},React.createElement('p',null,'内容'),React.createElement(DialogActions,null,React.createElement('button',{onClick:()=>saved++},'保存')),React.createElement(InfoTip,{text:'帮助说明'}))));
 assert(document.querySelector('dialog').open);assert.equal(document.querySelector('.ui-dialog-header h2').textContent,'设置');
 assert.equal(document.querySelector('.ui-dialog-body>button'),null);assert.equal(document.querySelector('.ui-dialog-footer button').textContent,'保存');
 await act(()=>document.querySelector('.ui-dialog-footer button').click());assert.equal(saved,1);
 assert.equal(document.querySelector('[role=tooltip]'),null);
 await act(()=>document.querySelector('.ui-info-trigger').focus());assert.equal(document.querySelector('[role=tooltip]').textContent,'帮助说明');
 await act(()=>document.querySelector('.ui-info-trigger').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})));assert.equal(document.querySelector('[role=tooltip]'),null);assert.equal(closed,0);
 await act(()=>document.querySelector('dialog').dispatchEvent(new Event('cancel',{cancelable:true})));assert.equal(closed,1);
 await act(()=>root.unmount());console.log('Dialog: footer actions, click handling, hover/focus help and cancel passed');
}finally{await rm(out,{force:true});dom.window.close();}

import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import React from 'react';
let slots=[],cursor=0,App,tree;
let project={id:'test',name:'测试剧',chapters:[{id:'season',title:'第1季',episodes:[{id:'ep0',title:'第00话',script:'正文',shots:[]},{id:'ep1',title:'第01话',script:'正文1',shots:[]}]}],assets:[]};
const hooks={...React,useEffect(){},useState(initial){const i=cursor++;if(!(i in slots))slots[i]=i===1?true:initial;return[slots[i],v=>slots[i]=typeof v==='function'?v(slots[i]):v];},useRef(initial){const i=cursor++;if(!(i in slots))slots[i]={current:initial};return slots[i];}};
const source=ts.transpileModule(readFileSync(new URL('../src/main.tsx',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.React,esModuleInterop:true}}).outputText;
globalThis.document={getElementById(){return {};}};
new Function('require','exports',source)(name=>{
 if(name==='react')return hooks;
 if(name==='react-dom/client')return{createRoot:()=>({render:element=>App=element.type})};
 if(name==='lucide-react')return new Proxy({},{get:(_,key)=>String(key)});
 if(name==='./useProject')return{useProject:()=>({project,current:{current:project},status:'已保存',flush:async()=>{},load:p=>{project=p;},edit(){}})};
 if(name==='./api')return{api:async()=>[],download:async()=>{}};
 if(name.endsWith('.css'))return{};
 if(name==='./SettingsPanel')return{__esModule:true,default:()=>null};
 return new Proxy({},{get:()=>()=>null});
},{});
function render(){cursor=0;tree=App();}
function nodes(v=tree){if(!v||typeof v!=='object')return[];if(Array.isArray(v))return v.flatMap(x=>nodes(x??null));return[v,...nodes(v.props?.children??null)];}
function text(v){if(v==null||typeof v==='boolean')return'';if(Array.isArray(v))return v.map(text).join('');if(typeof v==='object')return text(v.props?.children);return String(v);}
function click(label){const node=nodes().find(n=>n.type==='button'&&(n.props['aria-label']===label||text(n)===label));assert(node,`Missing button ${label}`);node.props.onClick();render();}
const crumb=()=>text(nodes().find(n=>n.props?.className==='breadcrumb'));
render();click('第00话');click('设置');assert.equal(crumb(),'测试剧设置');assert(!nodes().some(n=>n.props?.className==='episode-row selected'));
click('第00话');assert.equal(crumb(),'测试剧第00话');assert(nodes().some(n=>n.props?.className==='main-pane script-pane'));
click('设置');click('第01话');assert.equal(crumb(),'测试剧第01话');
click('资产库0');click('设置');click('返回工作区');assert.equal(crumb(),'测试剧资产库');
project=null;slots=[];render();click('设置');assert.equal(crumb(),'创作空间设置');click('返回工作区');assert(nodes().some(n=>n.props?.className==='library'));
console.log('Navigation: settings breadcrumb, same/different episode exit, previous page return and projectless exit passed');

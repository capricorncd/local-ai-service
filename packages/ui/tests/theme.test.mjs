import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/theme.ts',import.meta.url),'utf8');
const output=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const theme={};new Function('exports',output)(theme);
const saved=new Map(),style=new Map(),listeners={};
const system={matches:false,addEventListener(name,fn){this.change=fn;}};
globalThis.localStorage={getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)};
globalThis.document={documentElement:{dataset:{},style:{setProperty:(k,v)=>style.set(k,v)}}};
globalThis.window={addEventListener:(name,fn)=>listeners[name]=fn};
globalThis.matchMedia=()=>system;
for(const app of ['audio','image','story']){
 theme.initializeTheme(app);assert.equal(theme.getAppearance().mode,'system');
 assert.equal(document.documentElement.dataset.theme,'light');
 system.matches=true;system.change();assert.equal(document.documentElement.dataset.theme,'dark');
 theme.setAppearance({mode:'light',accent:'#ffffff'});assert.equal(document.documentElement.dataset.theme,'light');
 theme.initializeTheme(app);assert.equal(theme.getAppearance().accent,'#ffffff');
 assert.equal(theme.getAppearance().mode,'light');
 theme.resetAppearance();assert.equal(theme.getAppearance().mode,'system');assert.equal(theme.getAppearance().accent,theme.themeDefaults[app]);
 system.matches=false;system.change();
}
for(const color of ['#ffffff','#000000','#ffff00','#0000ff','#777777',...theme.themePresets.map(x=>x[1])]){
 assert(theme.contrast(color,theme.foreground(color))>=4.5);
 for(const dark of [false,true])assert(theme.contrast(theme.readableAccent(color,dark),dark?'#1b242c':'#ffffff')>=4.5);
}
assert.deepEqual(theme.readAppearance('{','bad'),{mode:'system',accent:'bad'});
assert.equal(theme.readAppearance('{"mode":"unknown","accent":"url(bad)"}','#16847d').accent,'#16847d');
listeners.storage({key:'local-ai-appearance-story',newValue:'{"mode":"dark","accent":"#3479cf"}'});
assert.equal(document.documentElement.dataset.theme,'dark');assert.equal(style.get('--ui-accent'),'#3479cf');
console.log('Theme: defaults, system changes, persistence, custom colors, contrast and storage updates passed');
assert.equal(theme.foreground('#16847d'),'#ffffff');

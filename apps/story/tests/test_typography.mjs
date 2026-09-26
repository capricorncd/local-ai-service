import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import ts from 'typescript';
import {JSDOM} from 'jsdom';
import postcss from 'postcss';
import remCss from '../scripts/rem-css.mjs';
const dom=new JSDOM('<!doctype html><html></html>',{url:'http://localhost'});
for(const k of ['window','document','localStorage'])globalThis[k]=dom.window[k];
const compiled=ts.transpileModule(readFileSync(new URL('../src/typography.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const settings={};new Function('exports',compiled)(settings);
settings.initializeTypography();assert.equal(settings.getTypography().fontSize,16);
settings.setTypography({fontSize:20,fontFamily:'Microsoft YaHei'});
assert.equal(document.documentElement.style.getPropertyValue('--story-font-size'),'20px');
settings.initializeTypography();assert.deepEqual(settings.getTypography(),{fontSize:20,fontFamily:'Microsoft YaHei'});
localStorage.setItem('local-ai-story-typography','invalid');settings.initializeTypography();assert.equal(settings.getTypography().fontSize,16);
const css=await postcss([remCss()]).process('button{width:120px;height:40px;padding:8px 12px;border-radius:8px;font-size:16px;background:url("data:test,16px")}@media(max-width:900px){button{width:100%}}',{from:undefined});
assert.match(css.css,/width:7.5rem;height:2.5rem;padding:0.5rem 0.75rem;border-radius:0.5rem;font-size:1rem/);
assert.match(css.css,/data:test,16px/);assert.match(css.css,/max-width:56.25rem/);
for(const file of readdirSync(new URL('../dist/assets/',import.meta.url)).filter(f=>f.endsWith('.css'))){
 const root=postcss.parse(readFileSync(new URL('../dist/assets/'+file,import.meta.url),'utf8'));
 root.walkDecls(d=>{assert.equal(remCssValue(d.value),d.value,`${file}: unscaled ${d.prop}`);});
}
function remCssValue(value){return value.replace(/url\([^)]*\)|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|(-?(?:\d*\.)?\d+)px\b/g,(m,n)=>n===undefined?m:'UNSCALED');}
console.log('Typography: default, persistence, invalid data fallback and built CSS scaling passed');
dom.window.close();

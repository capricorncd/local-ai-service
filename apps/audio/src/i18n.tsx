import React, {useSyncExternalStore} from 'react';
import {invoke, isTauri} from '@tauri-apps/api/core';
import en from './locales/en.json';
import zh from './locales/zh-CN.json';
import ja from './locales/ja.json';
type Language='zh-CN'|'en'|'ja';
export type LanguagePreference='system'|Language;
const languageNames:Record<Language,string>={'zh-CN':'简体中文',en:'English',ja:'日本語'};
const resolveLanguage=(value:string):Language=>value.toLowerCase().startsWith('zh')?'zh-CN':value.toLowerCase().startsWith('ja')?'ja':'en';
const listeners=new Set<()=>void>();
let preference:LanguagePreference='system';
try{const saved=localStorage.getItem('local-ai-ui-language');if(saved==='en'||saved==='zh-CN'||saved==='ja')preference=saved;}catch{}
let systemLanguage=resolveLanguage(navigator.language);
export const locale=()=>preference==='system'?systemLanguage:preference;
function notify(){document.documentElement.lang=locale();document.title=locale()==='en'?'Local AI · Service Manager':locale()==='ja'?'Local AI · サービス管理':'Local AI · 服务管理';listeners.forEach(fn=>fn());}
export function setLanguage(value:LanguagePreference){preference=value;try{localStorage.setItem('local-ai-ui-language',value);}catch{}notify();}
const originalByEnglish=Object.fromEntries(Object.entries(en).map(([zh,english])=>[english,zh]));
export function t(source:string,...values:unknown[]){source=originalByEnglish[source]??source;const dictionary:Record<string,string>=locale()==='ja'?ja:locale()==='en'?en:zh;const text=dictionary[source]??source;return text.replace(/\{(\d+)\}/g,(match,i)=>Number(i)<values.length?String(values[Number(i)]):match);}
export function serviceMessage(source:string){return source.split('；').map(part=>t(part)).join(locale()==='en'?'; ':'；');}
export function useLanguage(){useSyncExternalStore(fn=>{listeners.add(fn);return()=>{listeners.delete(fn);};},()=>preference+':'+systemLanguage);return{preference,language:locale(),setLanguage};}
async function updateSystem(){if(isTauri()){try{systemLanguage=resolveLanguage(await invoke<string>('system_language'));}catch{systemLanguage=resolveLanguage(navigator.language);}}else systemLanguage=resolveLanguage(navigator.language);notify();}
window.addEventListener('languagechange',updateSystem);window.addEventListener('focus',()=>{if(preference==='system')void updateSystem();});
window.addEventListener('storage',e=>{if(e.key==='local-ai-ui-language'){preference=e.newValue==='en'||e.newValue==='zh-CN'||e.newValue==='ja'?e.newValue:'system';notify();}});
notify();void updateSystem();
export function LanguageSettings(){const {preference,language,setLanguage}=useLanguage();return <section className="panel settings-panel"><h2>{t('界面语言')}</h2><label>{t('显示语言')}<select value={preference} onChange={e=>setLanguage(e.target.value as LanguagePreference)}><option value="system">{t('跟随系统')}</option>{Object.entries(languageNames).map(([code,name])=><option key={code} value={code}>{name}</option>)}</select></label><p className="muted">{t('当前语言：{0}',languageNames[language])} · {t('立即生效，无需重启。不会更改歌词、提示词或语音合成语言。')}</p></section>;}

export type UIPreferences={inputFontSize:number;assetColumnWidth:number;maximizeOnStart:boolean};
export const defaultUIPreferences:UIPreferences={inputFontSize:1,assetColumnWidth:12,maximizeOnStart:false};
let app:'story'|'image'|'audio'='story';
const key=()=>`local-ai-${app}-ui`;let current=defaultUIPreferences;const listeners=new Set<()=>void>();
export function parseUIPreferences(raw:string|null):UIPreferences{
 try{const value=JSON.parse(raw||'null');const clamp=(n:unknown,min:number,max:number,fallback:number)=>typeof n==='number'&&Number.isFinite(n)?Math.min(max,Math.max(min,n)):fallback;return {inputFontSize:clamp(value?.inputFontSize,.875,1.5,1),assetColumnWidth:clamp(value?.assetColumnWidth,8,24,12),maximizeOnStart:value?.maximizeOnStart===true};}catch{return {...defaultUIPreferences};}
}
function apply(){document.documentElement.dataset.uiApp=app;document.documentElement.style.setProperty('--ui-control-font-size',current.inputFontSize+'rem');document.documentElement.style.setProperty('--ui-resource-min-width',current.assetColumnWidth+'rem');document.documentElement.style.setProperty('--story-input-font-size',current.inputFontSize+'rem');document.documentElement.style.setProperty('--story-asset-column-width',current.assetColumnWidth+'rem');listeners.forEach(fn=>fn());}
export function initializeUIPreferences(application:'story'|'image'|'audio'='story'){app=application;try{current=parseUIPreferences(localStorage.getItem(key()));}catch{current={...defaultUIPreferences};}apply();window.addEventListener('storage',event=>{if(event.key===key()||event.key===null){current=parseUIPreferences(event.newValue);apply();}});}
export function setUIPreferences(value:UIPreferences){const next=parseUIPreferences(JSON.stringify(value));localStorage.setItem(key(),JSON.stringify(next));current=next;apply();}
export const getUIPreferences=()=>current;
export const subscribeUIPreferences=(fn:()=>void)=>{listeners.add(fn);return()=>{listeners.delete(fn);};};

export type Typography={fontSize:number;fontFamily:string};
export const defaultTypography:Typography={fontSize:16,fontFamily:''};
const key='local-ai-story-typography';
const listeners=new Set<()=>void>();
let current=defaultTypography;
export function parseTypography(raw:string|null):Typography{
  try{
    const v=JSON.parse(raw||'null');
    return {fontSize:typeof v?.fontSize==='number'&&Number.isFinite(v.fontSize)?Math.min(24,Math.max(12,Math.round(v.fontSize))):16,
      fontFamily:typeof v?.fontFamily==='string'&&v.fontFamily.length<=200&&!/[\x00-\x1f]/.test(v.fontFamily)?v.fontFamily:''};
  }catch{return {...defaultTypography};}
}
function apply(){
  const root=document.documentElement;
  // The root is the single pixel calibration; every UI length scales in rem.
  root.style.setProperty('--story-font-size',`${current.fontSize}px`);
  root.style.setProperty('--story-font-family',(current.fontFamily?JSON.stringify(current.fontFamily)+', ':'')+'system-ui, "Segoe UI", "Microsoft YaHei", sans-serif');
  listeners.forEach(fn=>fn());
}
export function initializeTypography(){
  try{current=parseTypography(localStorage.getItem(key));}catch{current={...defaultTypography};}
  apply();
  window.addEventListener('storage',event=>{if(event.key===key||event.key===null){current=parseTypography(event.newValue);apply();}});
}
export function setTypography(value:Typography){
  const next=parseTypography(JSON.stringify(value));
  // Report storage failures to the UI instead of claiming the setting was saved.
  localStorage.setItem(key,JSON.stringify(next));current=next;apply();
}
export const getTypography=()=>current;
export const subscribeTypography=(fn:()=>void)=>{listeners.add(fn);return()=>{listeners.delete(fn);};};

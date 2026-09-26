export type ThemeMode='system'|'light'|'dark';
export type Appearance={mode:ThemeMode;accent:string};
export const themeDefaults={audio:'#24745c',image:'#7860ce',story:'#16847d'};
export const themePresets=[['青绿','#16847d'],['森林','#24745c'],['海蓝','#3479cf'],['紫罗兰','#7860ce'],['琥珀','#b77918'],['玫红','#ba476d']] as const;
export function validColor(value:unknown):value is string{return typeof value==='string'&&/^#[0-9a-f]{6}$/i.test(value);}
export function readAppearance(value:string|null,accent:string):Appearance{
  try{const p=JSON.parse(value||'null');return {mode:['system','light','dark'].includes(p?.mode)?p.mode:'system',accent:validColor(p?.accent)?p.accent:accent};}
  catch{return {mode:'system',accent};}
}
function luminance(hex:string){
  const rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4);
  return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;
}
export function contrast(a:string,b:string){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
// Prefer white on filled buttons when it meets normal-text contrast.
export function foreground(accent:string){return contrast(accent,'#ffffff')>=4.5?'#ffffff':'#000000';}
export function readableAccent(accent:string,dark:boolean){
  const surface=dark?'#1b242c':'#ffffff',target=dark?255:0;
  const rgb=[1,3,5].map(i=>parseInt(accent.slice(i,i+2),16));
  for(let step=0;step<=20;step++){
    const color='#'+rgb.map(c=>Math.round(c+(target-c)*step/20).toString(16).padStart(2,'0')).join('');
    if(contrast(color,surface)>=4.5)return color;
  }
  return dark?'#ffffff':'#000000';
}
let app:keyof typeof themeDefaults='story';
let value:Appearance={mode:'system',accent:themeDefaults.story};
const subscribers=new Set<()=>void>();
let system:MediaQueryList|undefined;
let storageBound=false;
const key=()=>`local-ai-appearance-${app}`;
function apply(){
  const dark=value.mode==='dark'||value.mode==='system'&&!!system?.matches;
  const root=document.documentElement;
  root.dataset.theme=dark?'dark':'light';
  root.style.colorScheme=dark?'dark':'light';
  root.style.setProperty('--ui-accent',value.accent);
  root.style.setProperty('--ui-on-accent',foreground(value.accent));
  root.style.setProperty('--ui-accent-text',readableAccent(value.accent,dark));
}
export function initializeTheme(application:keyof typeof themeDefaults){
  app=application;
  let saved=null;try{saved=localStorage.getItem(key());}catch{/* Browser storage can be disabled. */}
  value=readAppearance(saved,themeDefaults[app]);
  if(!system){system=matchMedia('(prefers-color-scheme: dark)');system.addEventListener('change',apply);}
  if(!storageBound){window.addEventListener('storage',event=>{if(event.key===key()){value=readAppearance(event.newValue,themeDefaults[app]);apply();subscribers.forEach(fn=>fn());}});storageBound=true;}
  apply();
}
export function setAppearance(next:Appearance){
  value=readAppearance(JSON.stringify(next),themeDefaults[app]);apply();
  try{localStorage.setItem(key(),JSON.stringify(value));}catch{/* Keep the current session usable. */}
  subscribers.forEach(fn=>fn());
}
export function resetAppearance(){setAppearance({mode:'system',accent:themeDefaults[app]});}
export function getAppearance(){return value;}
export function subscribeAppearance(fn:()=>void){subscribers.add(fn);return()=>{subscribers.delete(fn);};}

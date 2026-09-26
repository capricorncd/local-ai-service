import {useEffect, useId, useRef, useState} from 'react';
import {Mic, Check} from 'lucide-react';
import {t} from './i18n';

export function MusicVoiceMenu({value,onChange,disabled}: {value:string;onChange:(value:string)=>void;disabled:boolean}) {
  const [open,setOpen]=useState(false);
  const root=useRef<HTMLDivElement>(null);
  const trigger=useRef<HTMLButtonElement>(null);
  const id=useId();
  const options=[['default','默认'],['male','男声'],['female','女声']];
  useEffect(()=>{if(!open)return;const outside=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside);},[open]);
  function focusOption(){requestAnimationFrame(()=>root.current?.querySelector<HTMLButtonElement>('[role="menuitemradio"][aria-checked="true"]')?.focus());}
  return <div ref={root} className="music-voice-menu" onMouseEnter={()=>{if(!disabled)setOpen(true);}} onMouseLeave={()=>setOpen(false)} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node))setOpen(false);}} onKeyDown={event=>{if(event.key==='Escape'){setOpen(false);trigger.current?.focus();}}}>
    <button ref={trigger} type="button" className="composer-tool" disabled={disabled} aria-haspopup="menu" aria-expanded={open&&!disabled} aria-controls={id} onClick={()=>{setOpen(true);focusOption();}} onKeyDown={event=>{if(event.key==='ArrowDown'){event.preventDefault();setOpen(true);focusOption();}}}><Mic size={18}/>{t('声音')}{value!=='default'&&<span className="voice-value">{t(value==='male'?'男声':'女声')}</span>}</button>
    {open&&!disabled&&<div className="voice-menu-popup" id={id} role="menu" aria-label={t('声音')} onKeyDown={event=>{if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;event.preventDefault();const items=Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button'));const index=items.indexOf(document.activeElement as HTMLButtonElement);items[event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus();}}>{options.map(([key,label])=><button type="button" role="menuitemradio" aria-checked={value===key} key={key} onClick={()=>{onChange(key);setOpen(false);trigger.current?.focus();}}><span>{t(label)}</span>{value===key&&<Check size={15}/>}</button>)}</div>}
  </div>;
}

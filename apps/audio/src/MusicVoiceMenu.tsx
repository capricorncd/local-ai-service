import {useEffect, useId, useLayoutEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {Mic, Check} from 'lucide-react';
import {t} from './i18n';

export function MusicVoiceMenu({value,onChange,disabled}: {value:string;onChange:(value:string)=>void;disabled:boolean}) {
  const [open,setOpen]=useState(false);
  const [position,setPosition]=useState({top:0,left:0,maxHeight:0});
  const root=useRef<HTMLDivElement>(null);
  const trigger=useRef<HTMLButtonElement>(null);
  const popup=useRef<HTMLDivElement>(null);
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const id=useId();
  const options=[['default','默认'],['male','男声'],['female','女声']];
  const contains=(node:Node|null)=>!!node&&(!!root.current?.contains(node)||!!popup.current?.contains(node));
  function keepOpen(){if(timer.current)clearTimeout(timer.current);}
  function close(){keepOpen();setOpen(false);}
  function leave(){keepOpen();timer.current=setTimeout(()=>setOpen(false),160);}
  useEffect(()=>()=>keepOpen(),[]);
  useEffect(()=>{if(disabled)close();},[disabled]);
  useLayoutEffect(()=>{
    if(!open||disabled)return;
    function place(){
      if(!trigger.current||!popup.current)return;
      const rect=trigger.current.getBoundingClientRect();
      const height=popup.current.scrollHeight;
      const below=window.innerHeight-rect.bottom-12,above=rect.top-12;
      const up=below<height&&above>below;
      const maxHeight=Math.max(0,up?above:below);
      const width=popup.current.getBoundingClientRect().width;
      setPosition({top:up?Math.max(8,rect.top-4-Math.min(height,maxHeight)):rect.bottom+4,left:Math.max(8,Math.min(rect.left,window.innerWidth-width-8)),maxHeight});
    }
    place();window.addEventListener('resize',place);window.addEventListener('scroll',place,true);
    return()=>{window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);};
  },[open,disabled]);
  useEffect(()=>{if(!open)return;const outside=(event:PointerEvent)=>{if(!contains(event.target as Node))close();};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside);},[open]);
  function focusOption(){requestAnimationFrame(()=>popup.current?.querySelector<HTMLButtonElement>('[role="menuitemradio"][aria-checked="true"]')?.focus());}
  return <div ref={root} className="music-voice-menu" onMouseEnter={()=>{keepOpen();if(!disabled)setOpen(true);}} onMouseLeave={leave} onBlur={event=>{if(!contains(event.relatedTarget as Node))close();}} onKeyDown={event=>{if(event.key==='Escape'){close();trigger.current?.focus();}}}>
    <button ref={trigger} type="button" className="composer-tool" disabled={disabled} aria-haspopup="menu" aria-expanded={open&&!disabled} aria-controls={id} onClick={()=>{keepOpen();setOpen(true);focusOption();}} onKeyDown={event=>{if(event.key==='ArrowDown'){event.preventDefault();keepOpen();setOpen(true);focusOption();}}}><Mic size={18}/>{t('声音')}{value!=='default'&&<span className="voice-value">{t(value==='male'?'男声':'女声')}</span>}</button>
    {open&&!disabled&&createPortal(<div ref={popup} className="voice-menu-popup" style={position} id={id} role="menu" aria-label={t('声音')} onMouseEnter={keepOpen} onMouseLeave={leave} onKeyDown={event=>{if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;event.preventDefault();const items=Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button'));const index=items.indexOf(document.activeElement as HTMLButtonElement);items[event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus();}}>{options.map(([key,label])=><button type="button" role="menuitemradio" aria-checked={value===key} key={key} onClick={()=>{onChange(key);close();trigger.current?.focus();}}><span>{t(label)}</span>{value===key&&<Check size={15}/>}</button>)}</div>,document.body)}
  </div>;
}

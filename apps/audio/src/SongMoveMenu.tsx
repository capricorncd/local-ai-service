import {useContext, useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {ChevronRight, Folder, FolderInput} from 'lucide-react';
import {SongMenuContext} from './SongMoreMenu';
import {t} from './i18n';

export function SongMoveMenu({groups,current,disabled,move}: {groups:string[];current:string;disabled:boolean;move:(group:string)=>Promise<void>}) {
  const menu=useContext(SongMenuContext);
  const trigger=useRef<HTMLButtonElement>(null);
  const popup=useRef<HTMLDivElement>(null);
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const [position,setPosition]=useState<{left:number;top:number;maxHeight:number}|null>(null);
  const destinations=[...new Set(['',...groups])].filter(group=>group!==current);
  function stay(){if(timer.current)clearTimeout(timer.current);menu.keepOpen();}
  function show(focus=false){
    if(disabled)return;
    stay();
    const rect=trigger.current!.getBoundingClientRect();
    const parent=trigger.current!.closest('.song-more-menu')!.getBoundingClientRect();
    const height=Math.min(300,window.innerHeight-16,Math.max(1,destinations.length)*36+12);
    setPosition({left:parent.right+224<window.innerWidth?parent.right+4:Math.max(8,parent.left-224),top:Math.max(8,Math.min(rect.top,window.innerHeight-height-8)),maxHeight:height});
    if(focus)requestAnimationFrame(()=>popup.current?.querySelector<HTMLButtonElement>('button')?.focus());
  }
  function leave(){if(timer.current)clearTimeout(timer.current);timer.current=setTimeout(()=>setPosition(null),180);}
  useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current);},[]);
  useEffect(()=>{if(position&&popup.current)return menu.register(popup.current);},[!!position]);
  return <><button ref={trigger} type="button" role="menuitem" data-menu-keep-open aria-haspopup="menu" aria-expanded={!!position} disabled={disabled} onMouseEnter={()=>show()} onMouseLeave={leave} onClick={()=>position?setPosition(null):show()} onKeyDown={e=>{if(e.key==='ArrowRight'){e.preventDefault();e.stopPropagation();show(true);}}}><FolderInput size={14}/>{t('移动至')}<ChevronRight size={14} style={{marginLeft:'auto'}}/></button>{position&&createPortal(<div ref={popup} className="song-more-menu song-move-submenu" role="menu" aria-label={t('移动至')} style={position} onMouseEnter={stay} onMouseLeave={e=>{leave();if(!menu.contains(e.relatedTarget as Node))menu.leave();}} onKeyDown={e=>{
    if(e.key==='ArrowLeft'){e.preventDefault();e.stopPropagation();setPosition(null);trigger.current?.focus();return;}
    if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;
    e.preventDefault();e.stopPropagation();
    const items=Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'));
    const index=items.indexOf(document.activeElement as HTMLButtonElement);
    items[e.key==='Home'?0:e.key==='End'?items.length-1:(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus();
  }}>{destinations.length?destinations.map(group=><button key={group} type="button" role="menuitem" disabled={disabled} onClick={()=>void move(group)}><Folder size={14}/><span>{group||t('未分组')}</span></button>):<p className="muted">{t('暂无其他工作区')}</p>}</div>,document.body)}</>;
}

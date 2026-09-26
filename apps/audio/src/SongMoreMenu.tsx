import {createContext, useEffect, useRef, useState, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {Ellipsis} from 'lucide-react';
import {t} from './i18n';

export const SongMenuContext=createContext({keepOpen:()=>{},leave:()=>{},register:(_node:HTMLElement)=>()=>{},contains:(_node:Node|null):boolean=>false});

export function SongMoreMenu({children}: {children:ReactNode}) {
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const submenus=useRef(new Set<HTMLElement>());
  const contains=(node:Node|null)=>!!node&&(!!popup.current?.contains(node)||[...submenus.current].some(menu=>menu.contains(node)));
  const register=(node:HTMLElement)=>{submenus.current.add(node);return()=>{submenus.current.delete(node);};};
  const timer = useRef<ReturnType<typeof setTimeout>|null>(null);
  const [position,setPosition] = useState<{top?:number;bottom?:number;left:number;maxHeight:number}|null>(null);
  function keepOpen() { if(timer.current) clearTimeout(timer.current); }
  function close() { keepOpen();setPosition(null); }
  function show(focus=false) {
    keepOpen();
    const rect=trigger.current!.getBoundingClientRect();
    const below=window.innerHeight-rect.bottom-12;
    const height=Math.min(300,Math.max(below,rect.top-12));
    setPosition({left:Math.max(8,Math.min(rect.right-192,window.innerWidth-200)),...(below>=height?{top:rect.bottom+4}:{bottom:window.innerHeight-rect.top+4}),maxHeight:height});
    if(focus) requestAnimationFrame(()=>popup.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus());
  }
  function leave() { keepOpen();timer.current=setTimeout(close,160); }
  useEffect(()=>()=>keepOpen(),[]);
  useEffect(()=>{
    if(!position)return;
    const outside=(e:Event)=>{if(!trigger.current?.contains(e.target as Node)&&!contains(e.target as Node))close();};
    const escape=(e:KeyboardEvent)=>{if(e.key==='Escape'){close();trigger.current?.focus();}};
    document.addEventListener('pointerdown',outside);
    document.addEventListener('keydown',escape);
    window.addEventListener('scroll',outside,true);
    window.addEventListener('resize',close);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);window.removeEventListener('scroll',outside,true);window.removeEventListener('resize',close);};
  },[!!position]);
  return <><button ref={trigger} type="button" className="song-more-trigger" aria-label={t('更多操作')} title={t('更多操作')} aria-haspopup="menu" aria-expanded={!!position} onMouseEnter={()=>show()} onMouseLeave={leave} onClick={()=>position?close():show()} onKeyDown={e=>{if(e.key==='ArrowDown'){e.preventDefault();show(true);}}}><Ellipsis size={20}/></button>{position&&createPortal(<SongMenuContext.Provider value={{keepOpen,leave,register,contains}}><div ref={popup} className="song-more-menu" role="menu" aria-label={t('更多操作')} style={position} onMouseEnter={keepOpen} onMouseLeave={leave} onBlur={e=>{if(!contains(e.relatedTarget as Node))close();}} onClick={e=>{const button=(e.target as Element).closest('button');if(button&&!button.disabled&&!button.hasAttribute('data-menu-keep-open'))close();}} onKeyDown={e=>{
    if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;
    e.preventDefault();
    const items=Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'));
    const index=items.indexOf(document.activeElement as HTMLButtonElement);
    const next=e.key==='Home'?0:e.key==='End'?items.length-1:(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;
    items[next]?.focus();
  }}>{children}</div></SongMenuContext.Provider>,document.body)}</>;
}


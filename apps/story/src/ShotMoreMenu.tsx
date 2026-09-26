import {useEffect,useRef} from 'react';
import {EllipsisVertical,Plus,Trash2} from 'lucide-react';
export function ShotMoreMenu({onInsert,onDelete}:{onInsert:()=>void;onDelete:()=>void|Promise<void>}){
 const ref=useRef<HTMLDetailsElement>(null);const timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);const keep=()=>clearTimeout(timer.current);const close=()=>{keep();ref.current?.removeAttribute('open');};
 useEffect(()=>{const outside=(e:PointerEvent)=>{if(!ref.current?.contains(e.target as Node))close();};document.addEventListener('pointerdown',outside);return()=>{keep();document.removeEventListener('pointerdown',outside);};},[]);
 return <details className="shot-more" ref={ref} onMouseEnter={()=>{keep();ref.current?.setAttribute('open','');}} onMouseLeave={()=>{timer.current=setTimeout(close,160);}} onKeyDown={e=>{if(e.key==='Escape'){close();ref.current?.querySelector('summary')?.focus();}}}><summary aria-label="分镜更多操作" title="更多操作"><EllipsisVertical size="1.125rem"/></summary><div className="shot-more-menu"><button type="button" onClick={()=>{close();onInsert();}}><Plus size="1rem"/>插入</button><button type="button" className="danger" onClick={()=>{close();void onDelete();}}><Trash2 size="1rem"/>删除</button></div></details>;
}

import {useEffect,useRef} from 'react';
import {EllipsisVertical,Trash2,Repeat2} from 'lucide-react';
export function ScriptMoreMenu({onDelete,onToggleKind,kind}:{onDelete:()=>void|Promise<void>;onToggleKind:()=>void;kind:'episode'|'special'}){
 const ref=useRef<HTMLDetailsElement>(null);
 useEffect(()=>{const outside=(event:PointerEvent)=>{if(!ref.current?.contains(event.target as Node))ref.current?.removeAttribute('open');};const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'&&ref.current?.open){ref.current.open=false;ref.current.querySelector('summary')?.focus();}};document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};},[]);
 return <details ref={ref} className="script-more"><summary aria-label="更多操作" title="更多操作"><EllipsisVertical size="1.125rem"/></summary><div className="script-more-menu"><button type="button" onClick={()=>{ref.current?.removeAttribute('open');onToggleKind();}}><Repeat2 size=".9375rem"/>{kind==='special'?'设为正篇':'设为特别篇'}</button><button type="button" className="script-delete" onClick={()=>{ref.current?.removeAttribute('open');void onDelete();}}><Trash2 size={15}/>删除当前话</button></div></details>;
}

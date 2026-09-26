import {useEffect,useRef} from 'react';
import {Ellipsis,Trash2} from 'lucide-react';
export function ScriptMoreMenu({onDelete}:{onDelete:()=>void|Promise<void>}){
 const ref=useRef<HTMLDetailsElement>(null);
 useEffect(()=>{const outside=(event:PointerEvent)=>{if(!ref.current?.contains(event.target as Node))ref.current?.removeAttribute('open');};const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'&&ref.current?.open){ref.current.open=false;ref.current.querySelector('summary')?.focus();}};document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};},[]);
 return <details ref={ref} className="script-more"><summary aria-label="更多操作" title="更多操作"><Ellipsis size={18}/></summary><div className="script-more-menu"><button type="button" className="script-delete" onClick={()=>{ref.current?.removeAttribute('open');void onDelete();}}><Trash2 size={15}/>删除当前话</button></div></details>;
}

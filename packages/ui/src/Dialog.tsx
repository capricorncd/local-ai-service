import {createContext,useContext,useEffect,useId,useRef,useState,type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {Info,X} from 'lucide-react';
import './dialog.css';
const FooterContext=createContext<HTMLDivElement|null>(null);
export function DialogActions({children}:{children:ReactNode}){const host=useContext(FooterContext);return host?createPortal(children,host):null;}
export function Dialog({title,children,footer,onClose,wide=false,info}:{title:ReactNode;children:ReactNode;footer?:ReactNode;onClose:()=>void;wide?:boolean;info?:ReactNode}){
 const ref=useRef<HTMLDialogElement>(null),id=useId();const [host,setHost]=useState<HTMLDivElement|null>(null);
 useEffect(()=>{const node=ref.current;node?.showModal();if(document.activeElement?.closest('.ui-info'))node?.focus();return()=>node?.close();},[]);
 return <dialog ref={ref} tabIndex={-1} className={'ui-dialog'+(wide?' ui-dialog-wide':'')} aria-labelledby={id} onCancel={e=>{e.preventDefault();onClose();}}>
 <div className="ui-dialog-layout"><div className="ui-dialog-header"><h2 id={id}>{title}</h2>{info}<button type="button" aria-label="关闭" onClick={onClose}><X size={20}/></button></div>
 <FooterContext.Provider value={host}><div className="ui-dialog-body">{children}</div></FooterContext.Provider>
 <div className="ui-dialog-footer" ref={setHost}>{footer}</div></div></dialog>;
}
export function InfoTip({text,inline=false,label='说明'}:{text:string;inline?:boolean;label?:string}){
 const id=useId(),trigger=useRef<HTMLSpanElement>(null);const [position,setPosition]=useState<{left:number;top:number}|null>(null);
 const show=()=>{const r=trigger.current?.getBoundingClientRect();if(r)setPosition({left:Math.max(12,Math.min(r.left,window.innerWidth-332)),top:r.bottom+8});};
 useEffect(()=>{if(!position)return;const close=()=>setPosition(null);window.addEventListener('resize',close);window.addEventListener('scroll',close,true);return()=>{window.removeEventListener('resize',close);window.removeEventListener('scroll',close,true);};},[position]);
 return <span ref={trigger} className="ui-info" onMouseEnter={show} onMouseLeave={()=>setPosition(null)} onFocus={show} onBlur={()=>setPosition(null)} onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();setPosition(null);}}}>
 {inline?<span tabIndex={0} className="ui-info-trigger" aria-label={label} aria-describedby={position?id:undefined} onClick={e=>e.stopPropagation()}><Info size={16}/></span>:<button type="button" className="ui-info-trigger" aria-label={label} aria-describedby={position?id:undefined}><Info size={16}/></button>}
 {position&&<span id={id} role="tooltip" className="ui-info-content" ref={node=>{if(node){const r=node.getBoundingClientRect();if(r.bottom>window.innerHeight-12)node.style.top=Math.max(12,(trigger.current?.getBoundingClientRect().top||0)-r.height-8)+'px';}}} style={position}>{text}</span>}</span>;
}

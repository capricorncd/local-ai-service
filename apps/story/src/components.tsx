import {Dialog,InfoTip} from '../../../packages/ui/src/Dialog';
import {Children,isValidElement,type ReactElement} from 'react';
import {MentionEditor,type MentionEditorHandle} from './MentionEditor';
import {mentionIds} from './mentionText';
import {createPortal} from 'react-dom';
import {useEffect,useLayoutEffect,useRef,useState,ReactNode} from 'react';
import {X,ChevronLeft,ChevronRight,Image as ImageIcon} from 'lucide-react';
import {request} from './api';
import {Asset} from './types';

export function Modal({title,children,onClose,wide=false,footer}:{title:string;children:ReactNode;onClose:()=>void;wide?:boolean;footer?:ReactNode}){
 const content=Children.toArray(children),isActions=(node:ReactNode)=>isValidElement<{className?:string}>(node)&&node.props.className==='actions';
 const hints=content.filter(node=>isValidElement<{className?:string}>(node)&&node.props.className==='hint');
 return <Dialog title={title} wide={wide} onClose={onClose} footer={footer??content.filter(isActions)} info={hints.map((node,i)=><InfoTip key={i} text={String((node as ReactElement<{children:ReactNode}>).props.children)}/>)}>{content.filter(node=>!isActions(node)&&!hints.includes(node))}</Dialog>;
}
export function Media({pid,path,audio=false,className=''}:{pid:string;path:string;audio?:boolean;className?:string}){
  const [url,setUrl]=useState(''),[error,setError]=useState('');
  useEffect(()=>{let disposed=false,object='';setUrl('');setError('');if(path)request(`/v1/projects/${pid}/${path}`).then(r=>r.blob()).then(b=>{if(disposed)return;object=URL.createObjectURL(b);setUrl(object);}).catch(()=>{if(!disposed)setError('素材读取失败');});return()=>{disposed=true;if(object)URL.revokeObjectURL(object);};},[pid,path]);
  return url?(audio?<audio controls src={url}/>:<img className={className} src={url} alt="素材预览"/>):<div className={'media-placeholder '+className}><ImageIcon size="1.5rem"/><small>{error||'暂无图片'}</small></div>;
}
export function Mention({value,onChange,assets,pid}:{value:string;onChange:(v:string,ids:string[])=>void;assets:Asset[];pid:string}){
  const ref=useRef<MentionEditorHandle>(null);const [cursor,setCursor]=useState(0);const [hover,setHover]=useState<{asset:Asset;rect:DOMRect}|null>(null);const [visible,setVisible]=useState(false);const [previewId,setPreviewId]=useState('');const popupRef=useRef<HTMLDivElement>(null);const [search,setSearch]=useState<string|null>(null);const [category,setCategory]=useState('all');const [position,setPosition]=useState({left:0,top:0,maxHeight:264,previewWidth:300});
  const match=value.slice(0,cursor).match(/@([^@\s\[\]()]{0,50})$/);
  const query=(search??match?.[1]??'').trim().toLowerCase();
  const results=visible&&match?assets.filter(a=>(category==='all'||a.kind===category)&&a.name.toLowerCase().includes(query)):[];
  useEffect(()=>{if(!visible)return;const outside=(event:PointerEvent)=>{if(!popupRef.current?.contains(event.target as Node)&&!ref.current?.contains(event.target as Node))setVisible(false);};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside);},[visible]);
  useLayoutEffect(()=>{
    if(!visible||!match)return;
    const place=()=>{const rect=ref.current?.getBoundingClientRect();if(!rect)return;const rem=parseFloat(getComputedStyle(document.documentElement).fontSize);const gap=.75*rem,margin=.75*rem,width=Math.min(20*rem,window.innerWidth-2*margin),height=Math.min(26*rem,window.innerHeight-2*margin);const left=Math.min(Math.max(rect.left,19.5*rem+margin),window.innerWidth-width-margin);const top=Math.max(margin,Math.min(rect.bottom+.25*rem,window.innerHeight-height-margin));setPosition({left,top,maxHeight:height,previewWidth:Math.max(0,Math.min(18.75*rem,left-gap-margin))});};
    place();window.addEventListener('resize',place);window.addEventListener('scroll',place,true);return()=>{window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);};
  },[visible,!!match]);

  function update(v:string){onChange(v,mentionIds(v,assets));}
  return <div className="mention-wrap"><MentionEditor ref={ref} value={value} assets={assets} onInput={(text,offset)=>{setCursor(offset);setVisible(true);setSearch(null);update(text);}} onCaret={setCursor} onEscape={()=>setVisible(false)} onHover={(asset,rect)=>setHover(asset&&rect?{asset,rect}:null)}/>{hover&&<MentionPreview pid={pid} asset={hover.asset} rect={hover.rect}/> }{visible&&match&&createPortal(<div ref={popupRef} style={{left:position.left,top:position.top,maxHeight:position.maxHeight}} className="mention-popup" onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();setVisible(false);ref.current?.focus();}}} onMouseLeave={()=>setPreviewId('')}><div className="mention-header"><div className="mention-heading"><strong>选择素材</strong><span>{results.length} 项</span><button type="button" aria-label="关闭素材选择" onClick={()=>{setVisible(false);ref.current?.focus();}}><X size="1rem"/></button></div><input type="search" aria-label="搜索素材" placeholder="搜索角色、场景或道具…" value={search??match[1]} onChange={e=>{setSearch(e.target.value);setPreviewId('');}}/><div className="mention-categories" role="group" aria-label="素材分类">{[['all','全部'],['character','角色'],['scene','场景'],['prop','道具']].map(([id,label])=><button type="button" key={id} aria-pressed={category===id} onClick={()=>{setCategory(id);setPreviewId('');}}>{label}</button>)}</div></div><div className="mentions" role="listbox" aria-label="匹配素材">{results.length?results.map(a=><button key={a.id} role="option" aria-selected={previewId===a.id} onMouseEnter={()=>setPreviewId(a.id)} onFocus={()=>setPreviewId(a.id)} onMouseDown={e=>e.preventDefault()} onClick={()=>{const insertion=`@[${a.name}](asset:${a.id}) `;const start=cursor-match[0].length;ref.current?.insert(start,cursor,insertion);setVisible(false);setHover(null);}}><Media pid={pid} path={a.image}/><span>{a.name}<small>{a.kind==='character'?'角色':a.kind==='scene'?'场景':'道具'}</small></span></button>):<p>没有匹配的素材，请调整搜索或分类。</p>}</div></div>,document.body)}</div>;
}

export function AssetDetails({pid,assets,initial,onClose}:{pid:string;assets:Asset[];initial:Asset;onClose:()=>void}){
 const items=[...new Map([...assets,initial].map(a=>[a.id,a])).values()];const [selected,setSelected]=useState(initial.id);const index=Math.max(0,items.findIndex(a=>a.id===selected));const asset=items[index];
 const move=(delta:number)=>setSelected(items[(index+delta+items.length)%items.length].id);
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.target instanceof HTMLInputElement||e.target instanceof HTMLTextAreaElement)return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();move(e.key==='ArrowLeft'?-1:1);}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[selected,items.map(a=>a.id).join(',')]);
 return <Modal wide title={asset.name} onClose={onClose} footer={<div className="asset-details-navigation"><button disabled={items.length<2} aria-label="上一个素材" onClick={()=>move(-1)}><ChevronLeft size="1rem"/>上一项</button><span>{index+1} / {items.length}</span><button disabled={items.length<2} aria-label="下一个素材" onClick={()=>move(1)}>下一项<ChevronRight size="1rem"/></button></div>}><div className="asset-details-content"><div className="asset-details-image"><Media key={asset.id} pid={pid} path={asset.image}/></div><div className="asset-details-text" key={asset.id}><p>{asset.kind==='character'?'角色':asset.kind==='scene'?'场景':'道具'}</p><dl>{([['描述',asset.description],['性别',asset.gender],['体型',asset.body],['形态',asset.form],['服饰',asset.clothing],['一致性要求',asset.constraints],['声音描述',asset.voice_description]]).filter(([,value])=>!!value).map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>{!asset.description&&<p>暂无描述</p>}{asset.voice&&<Media pid={pid} path={asset.voice} audio/>}</div></div></Modal>;
}
export function AssetThumbnail({pid,asset,references=[asset]}:{pid:string;asset:Asset;references?:Asset[]}){const [open,setOpen]=useState(false);return <div className="asset-thumbnail"><button type="button" className="asset-thumbnail-image" aria-label={'查看素材 '+asset.name} onClick={()=>setOpen(true)}><Media pid={pid} path={asset.image}/></button>{open&&<AssetDetails pid={pid} assets={references} initial={asset} onClose={()=>setOpen(false)}/>}</div>;}

function MentionPreview({pid,asset,rect}:{pid:string;asset:Asset;rect:DOMRect}){
 const rem=parseFloat(getComputedStyle(document.documentElement).fontSize);const margin=.75*rem,width=Math.min(12*rem,window.innerWidth-2*margin),height=8*rem;const left=Math.max(margin,Math.min(rect.left,window.innerWidth-width-margin));const top=rect.top>=height+margin?rect.top-height-.375*rem:Math.min(rect.bottom+.375*rem,window.innerHeight-height-margin);
 return createPortal(<div className="mention-thumbnail-preview" role="tooltip" aria-label={asset.name+' 缩略图'} style={{left,top,width,height}}><Media pid={pid} path={asset.image}/></div>,document.body);
}

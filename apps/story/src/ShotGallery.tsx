import {useEffect,useRef,useState} from 'react';
import {Image as ImageIcon,ChevronLeft,ChevronRight} from 'lucide-react';
import {Media,Modal} from './components';
import type {Job,Shot} from './types';

export function shotImages(shot:Shot,jobs:Job[]){return [...new Set([shot.image,...(shot.images||[]),...jobs.filter(j=>j.kind==='shot'&&j.target_id===shot.id&&j.status==='completed').map(j=>j.path)].filter(path=>!!path&&!shot.hidden_images?.includes(path)))];}
export function ShotGallery({pid,shot,jobs,onCover,onDelete,onDownload}:{pid:string;shot:Shot;jobs:Job[];onCover:(path:string,images:string[])=>void;onDelete:(path:string,images:string[])=>void;onDownload:(path:string)=>void}){
 const paths=shotImages(shot,jobs),[view,setView]=useState<string|null>(null),touch=useRef<number|null>(null);
 const index=Math.max(0,paths.indexOf(view||'')),path=paths[index];
 const move=(delta:number)=>setView(paths[(index+delta+paths.length)%paths.length]);
 useEffect(()=>{if(!view)return;const key=(event:KeyboardEvent)=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();move(event.key==='ArrowLeft'?-1:1);}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[view,paths.join('\n')]);
 return <>
 {paths.length?<button className="shot-gallery-cover" aria-label="查看分镜效果图大图" onClick={()=>setView(shot.image||paths[0])}><Media pid={pid} path={shot.image||paths[0]}/></button>:<div className="shot-gallery-empty"><ImageIcon size="2rem"/><span>暂无效果图</span></div>}
 {view&&path&&<Modal wide title={shot.title+' · 分镜效果图'} onClose={()=>setView(null)} footer={<div className="shot-gallery-footer"><span>{index+1} / {paths.length}</span><button onClick={()=>{const remaining=paths.filter(p=>p!==path);onDelete(path,remaining);setView(remaining[Math.min(index,remaining.length-1)]||null);}}>删除这张</button><button onClick={()=>onDownload(path)}>下载</button><button className="primary" disabled={shot.image===path} onClick={()=>onCover(path,paths)}>{shot.image===path?'当前封面':'设为封面'}</button></div>}><div className="shot-gallery">
 <div className="shot-gallery-stage" onTouchStart={event=>{touch.current=event.touches[0].clientX;}} onTouchEnd={event=>{if(touch.current!==null){const delta=event.changedTouches[0].clientX-touch.current;if(Math.abs(delta)>45)move(delta<0?1:-1);}touch.current=null;}}>
 <button aria-label="上一张" disabled={paths.length<2} onClick={()=>move(-1)}><ChevronLeft/></button><Media pid={pid} path={path}/><button aria-label="下一张" disabled={paths.length<2} onClick={()=>move(1)}><ChevronRight/></button>
 </div>
 <div className="shot-gallery-thumbs">{paths.map((p,i)=><button key={p} aria-label={'查看第 '+(i+1)+' 张'} aria-pressed={path===p} onClick={()=>setView(p)}><Media pid={pid} path={p}/>{shot.image===p&&<small>封面</small>}</button>)}</div>
 </div></Modal>}
 </>;
}

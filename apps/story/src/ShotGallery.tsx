import {useEffect,useRef,useState} from 'react';
import {Upload,ChevronLeft,ChevronRight} from 'lucide-react';
import {Media,Modal} from './components';
import type {Job,Shot} from './types';

export function shotImages(shot:Shot,jobs:Job[]){return [...new Set([shot.image,...(shot.images||[]),...jobs.filter(j=>j.kind==='shot'&&j.target_id===shot.id&&j.status==='completed').map(j=>j.path)].filter(path=>!!path&&!shot.hidden_images?.includes(path)))];}
export function ShotGallery({pid,shot,jobs,onCover,onDelete,onDownload,onImport}:{pid:string;shot:Shot;jobs:Job[];onCover:(path:string,images:string[])=>void;onDelete:(path:string,images:string[])=>void;onDownload:(path:string)=>void;onImport:(files:File[])=>void|Promise<void>}){
 const paths=shotImages(shot,jobs),[view,setView]=useState<string|null>(null),touch=useRef<number|null>(null);
 const fileInput=useRef<HTMLInputElement>(null),importLock=useRef(false);const [dragging,setDragging]=useState(false),[importing,setImporting]=useState(false),[importError,setImportError]=useState('');
 async function addFiles(files:File[]){if(!files.length||importLock.current)return;if(files.some(file=>!['image/png','image/jpeg','image/webp'].includes(file.type)&&!(/\.(png|jpe?g|webp)$/i.test(file.name)))){setImportError('请选择 PNG、JPG 或 WebP 图片');return;}importLock.current=true;setImporting(true);setImportError('');try{await onImport(files);}catch(e){setImportError(String(e));}finally{importLock.current=false;setImporting(false);}}
 const index=Math.max(0,paths.indexOf(view||'')),path=paths[index];
 const move=(delta:number)=>setView(paths[(index+delta+paths.length)%paths.length]);
 useEffect(()=>{if(!view)return;const key=(event:KeyboardEvent)=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();move(event.key==='ArrowLeft'?-1:1);}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[view,paths.join('\n')]);
 return <>
 <div className={'shot-image-drop'+(dragging?' dragging':'')} onDragOver={event=>{event.preventDefault();event.dataTransfer.dropEffect='copy';setDragging(true);}} onDragLeave={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node))setDragging(false);}} onDrop={event=>{event.preventDefault();event.stopPropagation();setDragging(false);void addFiles(Array.from(event.dataTransfer.files));}}>
 <input ref={fileInput} hidden type="file" multiple accept="image/png,image/jpeg,image/webp" onChange={event=>{const files=Array.from(event.target.files||[]);event.target.value='';void addFiles(files);}}/>
 {paths.length?<button className="shot-gallery-cover" aria-label="查看分镜效果图大图" title="查看大图，也可拖入图片添加" onClick={()=>setView(shot.image||paths[0])}><Media pid={pid} path={shot.image||paths[0]}/></button>:<button type="button" className="shot-gallery-empty" disabled={importing} aria-label="拖入图片或点击上传" title="拖入图片或点击上传" onClick={()=>fileInput.current?.click()}><Upload size="1.375rem"/><strong>拖入图片或点击上传</strong><small>PNG / JPG / WebP</small></button>}
 {importing&&<span className="shot-image-status" role="status">导入中…</span>}
 </div>{importError&&<p className="warning" role="alert">{importError}</p>}

 {view&&path&&<Modal wide title={shot.title+' · 分镜效果图'} onClose={()=>setView(null)} footer={<div className="shot-gallery-footer"><span>{index+1} / {paths.length}</span><button onClick={()=>{const remaining=paths.filter(p=>p!==path);onDelete(path,remaining);setView(remaining[Math.min(index,remaining.length-1)]||null);}}>删除这张</button><button onClick={()=>onDownload(path)}>下载</button><button className="primary" disabled={shot.image===path} onClick={()=>onCover(path,paths)}>{shot.image===path?'当前封面':'设为封面'}</button></div>}><div className="shot-gallery">
 <div className="shot-gallery-stage" onTouchStart={event=>{touch.current=event.touches[0].clientX;}} onTouchEnd={event=>{if(touch.current!==null){const delta=event.changedTouches[0].clientX-touch.current;if(Math.abs(delta)>45)move(delta<0?1:-1);}touch.current=null;}}>
 <button aria-label="上一张" disabled={paths.length<2} onClick={()=>move(-1)}><ChevronLeft/></button><Media pid={pid} path={path}/><button aria-label="下一张" disabled={paths.length<2} onClick={()=>move(1)}><ChevronRight/></button>
 </div>
 <div className="shot-gallery-thumbs">{paths.map((p,i)=><button key={p} aria-label={'查看第 '+(i+1)+' 张'} aria-pressed={path===p} onClick={()=>setView(p)}><Media pid={pid} path={p}/>{shot.image===p&&<small>封面</small>}</button>)}</div>
 </div></Modal>}
 </>;
}

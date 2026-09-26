import {confirmAction} from '../../../packages/ui/src/confirm';
import {Dialog,InfoTip} from '../../../packages/ui/src/Dialog';
import {useEffect,useRef,useState} from 'react';
import {History,Loader2,X} from 'lucide-react';
import {isTauri} from '@tauri-apps/api/core';
import {getCurrentWindow} from '@tauri-apps/api/window';
import {Button} from '../../../packages/ui/src/index';
import {api} from './api';
import {loadImage,modes,parseProject,type Project} from './project';

type RecordItem={id:string;created:number;name:string;mode:Project['mode'];prompt:string;layers:number};
export function RecentOperations({project,connected,restore,notify}:{project:Project;connected:boolean;restore:(p:Project)=>void;notify:(e:unknown)=>void}) {
  const [open,setOpen]=useState(false),[records,setRecords]=useState<RecordItem[]>([]),[loading,setLoading]=useState(false),[opening,setOpening]=useState(false),[status,setStatus]=useState('');
  const [selectedId,setSelectedId]=useState('');
  const current=useRef(project),initial=useRef(project),recovered=useRef(false),timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),queue=useRef<Promise<unknown>>(Promise.resolve()),restored=useRef<Project|null>(null),closed=useRef(false);
  current.current=project;
  const meaningful=(p:Project)=>p!==initial.current||p.layers.length>0||p.prompt.trim()!==''||p.mask!==null||p.name!=='未命名工程';
  function save(p:Project) {
    clearTimeout(timer.current);
    if(!meaningful(p))return queue.current;
    setStatus('正在保存…');
    const task=queue.current.catch(()=>{}).then(()=>api('/v1/recents',{method:'POST',body:JSON.stringify(parseProject(p))}));
    queue.current=task;
    void task.then(()=>setStatus('已自动保存')).catch(()=>setStatus('保存失败，请重试'));
    return task;
  }
  useEffect(()=>{
    if(!connected||!meaningful(project)||restored.current===project)return;
    setStatus('等待保存…');
    timer.current=setTimeout(()=>{void save(project).catch(()=>{});},1500);
    return()=>clearTimeout(timer.current);
  },[project,connected]);
  useEffect(()=>{
    if(!connected||recovered.current)return;
    recovered.current=true;
    void(async()=>{
      try {
        const list=await api<RecordItem[]>('/v1/recents');
        if(!list.length||current.current!==initial.current)return;
        const next=parseProject(await api('/v1/recents/'+list[0].id));
        await Promise.all([...next.layers.map(l=>loadImage(l.source)),...(next.mask?[loadImage(next.mask)]:[])]);
        // Never replace edits made while the service or large images were loading.
        if(current.current!==initial.current)return;
        restored.current=next;restore(next);setStatus('已恢复上次操作');
      }catch(e){notify(e);}
    })();
  },[connected]);
  useEffect(()=>{
    if(!isTauri())return;
    let dispose:(()=>void)|undefined,unmounted=false;
    void getCurrentWindow().onCloseRequested(async event=>{
      event.preventDefault();
      if(closed.current)return;
      closed.current=true;
      try {await save(current.current);await getCurrentWindow().destroy();}
      catch(e){closed.current=false;notify(e);if(await confirmAction('最近记录保存失败。是否仍然关闭？未保存内容可先导出工程。'))await getCurrentWindow().destroy();}
    }).then(fn=>{if(unmounted)fn();else dispose=fn;});
    return()=>{unmounted=true;dispose?.();};
  },[]);
  async function show() {
    setOpen(true);setSelectedId('');setLoading(true);
    try {await save(current.current);setRecords(await api<RecordItem[]>('/v1/recents'));}
    catch(e){notify(e);}finally{setLoading(false);}
  }
  async function select(id:string) {
    setOpening(true);
    try {
      // Read first: saving the current canvas may evict the 30th snapshot.
      const next=parseProject(await api('/v1/recents/'+id));
      await Promise.all([...next.layers.map(l=>loadImage(l.source)),...(next.mask?[loadImage(next.mask)]:[])]);
      await save(current.current);
      restored.current=next;restore(next);setOpen(false);setStatus('已打开历史记录');
      notify('已恢复当时的图层、遮罩、提示词和生成参数');
    }catch(e){notify(e);}finally{setOpening(false);}
  }
  return <><Button onClick={()=>void show()} title={`最近 30 条操作记录${status?' · '+status:''}`}><History size={16}/>最近记录{status&&<span className={`autosave-dot ${status.includes('失败')?'failed':status.includes('保存…')?'pending':''}`} role="status" aria-label={status}/>}</Button>
    {open&&<Dialog title={<>最近记录 <small>{records.length} / 30</small></>} onClose={()=>{if(!opening)setOpen(false);}} info={<InfoTip text="编辑停顿后自动保存，保留最近 30 条。选择记录后，点击底部按钮恢复当时的完整操作内容。"/>} footer={<><span role="status" style={{marginRight:'auto'}}>{status}</span><Button disabled={opening} onClick={()=>setOpen(false)}>取消</Button><Button variant="primary" disabled={opening||!selectedId||loading} onClick={()=>void select(selectedId)}>{opening?'恢复中…':'恢复记录'}</Button></>}>
      {loading?<p><Loader2 size={16} className="spin"/> 正在读取…</p>:!records.length?<p className="muted">暂无记录，添加图片或输入提示词后会自动保存。</p>:<div className="recent-list">{records.map(r=><button key={r.id} disabled={opening} className="recent-entry" aria-pressed={selectedId===r.id} onClick={()=>setSelectedId(r.id)}>
        <div><strong>{r.name}</strong><time>{new Date(r.created*1000).toLocaleString()}</time></div>
        <span>{modes[r.mode]} · {r.layers} 个图层</span><p>{r.prompt||'未填写提示词'}</p>
      </button>)}</div>}
    </Dialog>}
  </>;
}

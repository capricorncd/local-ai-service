import {useEffect,useRef,useState} from 'react';
import {isTauri} from '@tauri-apps/api/core';
import {getCurrentWindow} from '@tauri-apps/api/window';
import {api} from './api';
import {Project} from './types';

export function sameProjectContent(a:Project|null,b:Project|null){
  if(a===b)return true;
  if(!a||!b)return false;
  const content=(p:Project)=>{const {revision,updated,...value}=p;return JSON.stringify(value);};
  return content(a)===content(b);
}

export function useProject(onError:(e:unknown)=>void){
  const [project,setProject]=useState<Project|null>(null), [status,setStatus]=useState('已保存');
  const current=useRef<Project|null>(null),saved=useRef<Project|null>(null),flight=useRef<Promise<void>|null>(null);
  const load=(p:Project|null)=>{current.current=p;saved.current=p;setProject(p);setStatus('已保存');};
  const edit=(fn:(p:Project)=>void)=>{
    if(!current.current)return;
    const next=structuredClone(current.current);fn(next);
    if(sameProjectContent(next,current.current))return;
    current.current=next;setProject(next);
    if(!flight.current&&sameProjectContent(next,saved.current)){
      setStatus('已保存');localStorage.removeItem('story-draft-'+next.id);return;
    }
    setStatus('等待保存');
    try{localStorage.setItem('story-draft-'+next.id,JSON.stringify(next));}catch{setStatus('等待保存（本地草稿空间不足）');}
  };
  const flush=async()=>{
    if(flight.current)await flight.current;
    if(!current.current||sameProjectContent(current.current,saved.current))return;
    const operation=async()=>{
      while(current.current&&!sameProjectContent(current.current,saved.current)){
        const captured=current.current;setStatus('保存中…');
        const result=await api<Project>('/v1/projects/'+captured.id,{method:'PUT',body:JSON.stringify(captured)});
        if(current.current===captured){current.current=result;saved.current=result;setProject(result);localStorage.removeItem('story-draft-'+result.id);}
        else if(current.current?.id===captured.id){current.current={...current.current,revision:result.revision,updated:result.updated};saved.current=result;setProject(current.current);}
      }
      setStatus('已保存');
    };
    flight.current=operation();
    try{await flight.current;}catch(e){setStatus('保存失败 · 草稿已保留');throw e;}finally{flight.current=null;}
  };
  const flushRef=useRef(flush);flushRef.current=flush;
  useEffect(()=>{if(!project||sameProjectContent(project,saved.current))return;const timer=setTimeout(()=>flushRef.current().catch(onError),900);return()=>clearTimeout(timer);},[project]);
  useEffect(()=>{
    const timer=setInterval(async()=>{
      const before=current.current;
      if(!before||!sameProjectContent(before,saved.current)||flight.current)return;
      try{const next=await api<Project>('/v1/projects/'+before.id);if(current.current===before&&next.revision>before.revision)load(next);}catch{/* autosave and explicit actions surface connection errors */}
    },4000);
    return()=>clearInterval(timer);
  },[]);
  useEffect(()=>{
    const unload=(e:BeforeUnloadEvent)=>{if(!sameProjectContent(current.current,saved.current)){e.preventDefault();e.returnValue='';}};
    window.addEventListener('beforeunload',unload);
    let dispose:(()=>void)|undefined;let cancelled=false;
    if(isTauri())getCurrentWindow().onCloseRequested(async e=>{e.preventDefault();try{await flushRef.current();await getCurrentWindow().destroy();}catch(err){onError(err);}}).then(f=>{if(cancelled)f();else dispose=f;});
    return()=>{cancelled=true;dispose?.();window.removeEventListener('beforeunload',unload);};
  },[]);
  return {project,current,load,edit,flush,status};
}

import {invoke,isTauri} from '@tauri-apps/api/core';
import {save,open} from '@tauri-apps/plugin-dialog';
let connection:{base:string;token:string}|undefined;
export async function request(path:string,init?:RequestInit){
  if(!connection)connection=isTauri()?await invoke('connection'):{base:'http://127.0.0.1:19878',token:sessionStorage.getItem('story-token')||''};
  const headers=new Headers(init?.headers);headers.set('Authorization',`Bearer ${connection!.token}`);
  if(init?.body&&!(init.body instanceof FormData))headers.set('Content-Type','application/json');
  const method=init?.method||'GET';
  const url=connection!.base+path;
  let res:Response;
  try{res=await fetch(url,{...init,headers});}
  catch(error){
    console.error('[Story API] Network failure', {method,url:url.split('?')[0],error:String(error)});
    throw Error(`无法连接剧本服务：${method} ${url.split('?')[0]}。请检查服务日志 launcher.log。`);
  }
  if(!res.ok){console.error('[Story API] HTTP failure',{method,path:path.split('?')[0],status:res.status});const e=await res.json().catch(()=>({detail:res.statusText}));throw Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail));}
  return res;
}
export const api=async<T=any>(path:string,init?:RequestInit):Promise<T>=>(await request(path,init)).json();
export const post=<T=any>(path:string,data:unknown)=>api<T>(path,{method:'POST',body:JSON.stringify(data)});
export function setToken(token:string){sessionStorage.setItem('story-token',token);connection=undefined;}
export async function pickDirectory(){return isTauri()?await open({directory:true,multiple:false}):null;}
export async function upload(path:string,file:File){const form=new FormData();form.append('file',file);return api(path,{method:'POST',body:form});}
export async function download(blob:Blob,name:string){
  if(isTauri()){const path=await save({defaultPath:name});if(path)await invoke('save_download',new Uint8Array(await blob.arrayBuffer()),{headers:{'x-save-path':JSON.stringify(path)}});}
  else{const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
}

export function setMobileToken(token:string){localStorage.setItem("story-mobile-token",token);connection={base:location.origin,token};}

import {invoke,isTauri} from '@tauri-apps/api/core';
import {save} from '@tauri-apps/plugin-dialog';
type Connection={base:string;token:string};
let current:Connection|undefined;
export async function connect(){
  if(isTauri())current=await invoke<Connection>('connection');
  else {const token=sessionStorage.getItem('image-token');if(!token)throw Error('浏览器预览需要填写图片服务 API Token');current={base:'http://127.0.0.1:19877',token};}
}
export async function request(path:string,init?:RequestInit){
  if(!current)await connect();
  const headers=new Headers(init?.headers);headers.set('Authorization',`Bearer ${current!.token}`);
  if(init?.body&&!(init.body instanceof FormData))headers.set('Content-Type','application/json');
  const r=await fetch(current!.base+path,{...init,headers});
  if(!r.ok){const e=await r.json().catch(()=>({detail:r.statusText}));throw Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail));}return r;
}
export async function api<T=any>(path:string,init?:RequestInit):Promise<T>{return (await request(path,init)).json();}
export async function upload(blob:Blob,name='reference.png'){const data=new FormData();data.append('file',blob,name);return api<{id:string;width:number;height:number;name:string}>('/v1/images',{method:'POST',body:data});}
export async function download(blob:Blob,name:string){
  if(isTauri()){const path=await save({defaultPath:name});if(path)await invoke('save_download',new Uint8Array(await blob.arrayBuffer()),{headers:{'x-save-path':JSON.stringify(path)}});}
  else{const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
}

import {createRoot} from 'react-dom/client';
import {Dialog} from './Dialog';
export function confirmAction(message:string):Promise<boolean>{
 return new Promise(resolve=>{const host=document.createElement('div');document.body.append(host);const root=createRoot(host);let finished=false;
 const finish=(value:boolean)=>{if(finished)return;finished=true;resolve(value);queueMicrotask(()=>{root.unmount();host.remove();});};
 root.render(<Dialog title="确认操作" onClose={()=>finish(false)} footer={<><button type="button" onClick={()=>finish(false)} autoFocus>取消</button><button type="button" className="button primary" onClick={()=>finish(true)}>确定</button></>}><p>{message}</p></Dialog>);
 });
}

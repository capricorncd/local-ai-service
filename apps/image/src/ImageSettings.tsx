import {useState} from 'react';
import {isTauri} from '@tauri-apps/api/core';
import {AppearanceSettings,Button} from '../../../packages/ui/src/index';
import {DialogActions} from '../../../packages/ui/src/Dialog';
import {ModelConfiguration,type Result} from './ModelConfiguration';

const tabs=[['models','模型文件'],['runtime','运行环境'],['appearance','外观设置'],['connection','服务连接']] as const;
export function ImageSettings({config,onSaved,token,setToken,onConnect,notify}:{config:Result|null;onSaved:(value:Result)=>void;token:string;setToken:(value:string)=>void;onConnect:()=>void;notify:(value:unknown)=>void}){
  const [active,setActive]=useState<string>('models');
  return <div className="image-settings">
    <div className="image-settings-tabs" role="tablist" aria-label="设置分类">
      {tabs.map(([id,label],index)=><button key={id} type="button" role="tab" id={'image-tab-'+id} aria-controls={'image-panel-'+id} aria-selected={active===id} tabIndex={active===id?0:-1} onClick={()=>setActive(id)} onKeyDown={event=>{
        if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
        event.preventDefault();
        const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
        setActive(tabs[next][0]);
        event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
      }}>{label}</button>)}
    </div>
    {config?<ModelConfiguration value={config} onSaved={onSaved} notify={notify} activeTab={active}/>:tabs.slice(0,2).map(([id])=><div key={id} role="tabpanel" id={'image-panel-'+id} aria-labelledby={'image-tab-'+id} hidden={active!==id}><p role="status">等待服务连接…</p><Button onClick={()=>setActive('connection')}>前往服务连接</Button></div>)}
    <div role="tabpanel" id="image-panel-appearance" aria-labelledby="image-tab-appearance" hidden={active!=='appearance'}>
      {active==='appearance'&&<AppearanceSettings dialogActions/>}
    </div>
    <div role="tabpanel" id="image-panel-connection" aria-labelledby="image-tab-connection" hidden={active!=='connection'}>
      <p className="settings-help">本地服务地址：127.0.0.1:19877。模型按需加载，任务结束释放显存。</p>
      {isTauri()?<p>桌面应用自动连接本地服务，无需填写 API Token。</p>:<label htmlFor="image-api-token"><span>API Token <span className="required-mark">必填</span></span><input id="image-api-token" type="password" required aria-invalid={!token.trim()} aria-describedby={!token.trim()?'image-token-error':undefined} value={token} onChange={e=>setToken(e.target.value)}/>{!token.trim()&&<small id="image-token-error" className="field-error">请输入图片服务 API Token</small>}{active==='connection'&&<DialogActions><Button disabled={!token.trim()} onClick={onConnect}>连接</Button></DialogActions>}</label>}
    </div>
  </div>;
}

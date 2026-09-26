import {DialogActions} from '../../../packages/ui/src/Dialog';
import {useEffect, useState} from 'react';
import {Check, FolderOpen, Loader2, X} from 'lucide-react';
import {open} from '@tauri-apps/plugin-dialog';
import {Button} from '../../../packages/ui/src/index';
import {api} from './api';

type Configuration = Record<string, string>;
type Result = {
  config: Configuration;
  models: {role: string; ready: boolean; error: string | null}[];
  runtime_ready: boolean;
  runtime_checks?: {python: boolean; core: boolean};
};
const fields = [['model_dir','模型目录'],['model','主模型文件'],['vae','VAE 文件'],['encoder','视觉文本编码器'],['python','图片推理 Python'],['core','图片推理代码目录']];

export function ModelConfiguration({value,onSaved,notify}:{value:Result;onSaved:(v:Result)=>void;notify:(v:unknown)=>void}) {
  const [draft,setDraft]=useState(value.config),[saving,setSaving]=useState(false);
  useEffect(()=>setDraft(value.config),[value]);
  function status(key:string) {
    if(key==='model_dir')return null;
    const model=value.models.find(m=>m.role===key);
    const changed=draft[key]!==value.config[key] || (!!model && draft.model_dir!==value.config.model_dir);
    const ready=model ? model.ready : (value.runtime_checks?.[key as 'python'|'core'] ?? value.runtime_ready);
    const text=changed?'待保存检查':model?(ready?'已找到完整文件':'文件不可用'):(ready?'已配置':'未配置');
    const detail=changed?'保存后重新检查':model?.error || (ready?text:'请检查路径，或运行图片应用的环境安装脚本');
    return <span className={`field-status ${changed?'pending':ready?'valid':'invalid'}`} title={detail} role="status">
      {!changed&&(ready?<Check size={13}/>:<X size={13}/>)}{text}
    </span>;
  }
  async function browse(key:string) {
    try {
      const directory=key==='model_dir'||key==='core';
      const selected=await open({directory,multiple:false,...(!directory?{filters:[{name:key==='python'?'Python':'Safetensors',extensions:key==='python'?['exe']:['safetensors']}]}:{})});
      if(typeof selected==='string')setDraft(old=>({...old,[key]:selected}));
    } catch(e){notify(e);}
  }
  async function save() {
    setSaving(true);
    try {onSaved(await api<Result>('/v1/config',{method:'PUT',body:JSON.stringify(draft)}));notify('配置已保存，新任务生效');}
    catch(e){notify(e);}finally{setSaving(false);}
  }
  return <>
    <div className="model-fields">{fields.map(([key,label])=><label key={key}>
      <span className="field-label"><span>{label}</span>{status(key)}</span>
      <div className="model-path-picker"><input value={draft[key]} disabled={saving} onChange={e=>setDraft({...draft,[key]:e.target.value})}/><Button disabled={saving} aria-label={`选择${label}`} onClick={()=>void browse(key)}><FolderOpen size={16}/></Button></div>
    </label>)}</div>
    <DialogActions><Button variant="primary" disabled={saving} onClick={()=>void save()}>
      {saving&&<Loader2 size={15} className="spin"/>}{saving?'保存中…':'保存配置'}
    </Button></DialogActions>
  </>;
}

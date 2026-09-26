import {DialogActions} from '../../../packages/ui/src/Dialog';
import {useEffect, useState} from 'react';
import {Check, FolderOpen, Loader2, X} from 'lucide-react';
import {open} from '@tauri-apps/plugin-dialog';
import {Button} from '../../../packages/ui/src/index';
import {api} from './api';

type Configuration = Record<string, string>;
export type Result = {
  config: Configuration;
  models: {role: string; ready: boolean; error: string | null}[];
  runtime_ready: boolean;
  runtime_checks?: {python: boolean; core: boolean};
};
const fields = [['model_dir','模型目录'],['model','主模型文件'],['vae','VAE 文件'],['encoder','视觉文本编码器'],['python','图片推理 Python'],['core','图片推理代码目录']];
const absolutePath=(path:string)=>/^(?:[a-z]:[\\/]|\\\\[^\\]+\\[^\\]+|\/)/i.test(path);
export function ModelConfiguration({value,onSaved,notify,activeTab}:{value:Result;onSaved:(v:Result)=>void;notify:(v:unknown)=>void;activeTab:string}) {
  const [draft,setDraft]=useState(value.config),[saving,setSaving]=useState(false);
  useEffect(()=>setDraft(value.config),[value]);
  const directoryRequired=['model','vae','encoder'].some(key=>!absolutePath(draft[key]||''));
  function fieldState(key:string) {
    const required=key!=='model_dir'||directoryRequired;
    if(required&&!draft[key]?.trim())return {required,state:'invalid',text:'必填项未填写',detail:key==='model_dir'?'使用相对文件名时，请填写模型目录；也可以为所有模型选择完整路径。':'请填写路径或使用右侧按钮选择。'};
    if(key==='model_dir')return {required,state:draft[key]!==value.config[key]?'pending':'',text:draft[key]!==value.config[key]?'待保存检查':'',detail:''};
    const model=value.models.find(m=>m.role===key);
    const changed=draft[key]!==value.config[key] || (!!model && !absolutePath(draft[key]||'') && draft.model_dir!==value.config.model_dir);
    const ready=model ? model.ready : (value.runtime_checks?.[key as 'python'|'core'] ?? value.runtime_ready);
    const text=changed?'待保存检查':model?(ready?'已找到完整文件':'文件不可用'):(ready?'已配置':'未配置');
    return {required,state:changed?'pending':ready?'valid':'invalid',text,detail:changed?'保存后重新检查':model?.error || (ready?text:'请检查路径，或运行图片应用的环境安装脚本')};
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
    {(['models','runtime'] as const).map(tab=><div key={tab} role="tabpanel" id={'image-panel-'+tab} aria-labelledby={'image-tab-'+tab} hidden={activeTab!==tab}>
      <p className="settings-help">{tab==='models'?'配置生成图片所需的模型。所有模型均使用完整路径时，模型目录可留空。':'配置图片推理使用的 Python 和代码目录。'} 红色边框表示需要补充或修正，黄色表示待保存检查。</p>
      <div className="model-fields">{fields.filter(([key])=>tab==='runtime'?['python','core'].includes(key):!['python','core'].includes(key)).map(([key,label])=>{
        const status=fieldState(key),id='image-config-'+key;
        return <label key={key} htmlFor={id}>
          <span className="field-label"><span>{label} {status.required&&<span className="required-mark">必填</span>}</span><span className={'field-status '+status.state} title={status.detail} role="status">{status.state==='valid'?<Check size={13}/>:status.state==='invalid'?<X size={13}/>:null}{status.text}</span></span>
          <div className="model-path-picker"><input id={id} value={draft[key]||''} required={status.required} aria-invalid={status.state==='invalid'} aria-describedby={status.state==='invalid'?id+'-error':undefined} className={status.state==='pending'?'field-pending':undefined} disabled={saving} onChange={e=>setDraft({...draft,[key]:e.target.value})}/><Button disabled={saving} aria-label={'选择'+label} onClick={()=>void browse(key)}><FolderOpen size={16}/></Button></div>
          {status.state==='invalid'&&<small id={id+'-error'} className="field-error">{status.detail}</small>}
        </label>;
      })}</div>
    </div>)}
    {['models','runtime'].includes(activeTab)&&<DialogActions><Button variant="primary" disabled={saving} onClick={()=>void save()}>
      {saving&&<Loader2 size={15} className="spin"/>}{saving?'保存中…':'保存配置'}
    </Button></DialogActions>}
  </>;
}

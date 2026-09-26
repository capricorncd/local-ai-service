import {useDraft, useDraftFile} from './useDraft';
import {ReferenceMedia, uploadReference} from './ReferenceMedia';
import {PlaybackMark} from './PlaybackMark';
import {useEffect, useState} from 'react';
import {Download, Play, Settings2} from 'lucide-react';
import {t} from './i18n';

export function TtsPanel({api, online, configure, submitted, media}: {api:(path:string,options?:RequestInit)=>Promise<any>;online:boolean;configure:()=>void;submitted:()=>void;media:(url:string,name:string)=>void}) {
  const [model,setModel]=useDraft('TtsPanel.tsx:model', 'qwen3-tts');
  const [mode,setMode]=useDraft('TtsPanel.tsx:mode', 'preset');
  const [text,setText]=useDraft('TtsPanel.tsx:text', '');
  const [language,setLanguage]=useDraft('TtsPanel.tsx:language', 'Chinese');
  const [speaker,setSpeaker]=useDraft('TtsPanel.tsx:speaker', 'vivian');
  const [instruct,setInstruct]=useDraft('TtsPanel.tsx:instruct', '');
  const [reference,setReference]=useDraftFile('TtsPanel.tsx:reference');
  const [referenceText,setReferenceText]=useDraft('TtsPanel.tsx:referenceText', '');
  const [info,setInfo]=useState<any>(null);
  const [voices,setVoices]=useState<any[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [cfg,setCfg]=useDraft('TtsPanel.tsx:cfg', 4);
  const breeze=model==='breeze-tts2';
  useEffect(()=>{if(!online)return;let stopped=false;let running=false;async function poll(){if(running)return;running=true;try{const data=await api('/v1/tts/models');if(!stopped)setInfo(data);}catch(e){if(!stopped)setError(String(e));}finally{running=false;}}void poll();const timer=setInterval(poll,1500);api('/v1/voices').then(v=>{if(!stopped)setVoices(v);}).catch(e=>{if(!stopped)setError(String(e));});return()=>{stopped=true;clearInterval(timer);};},[online]);
  const current=info?.models?.find((m:any)=>m.id===model);
  const download=info?.download;
  const ready=current?.status==='ready';
  async function action(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function generate(){await action(async()=>{
    let reference_upload_id;
    if(mode==='reference' && reference){reference_upload_id=await uploadReference(reference,api);}
    const request={model,text,language,seed:42,...(reference_upload_id?{reference_upload_id,reference_text:referenceText}:breeze?{}:{speaker}),...((breeze||mode==='preset')?{instruct}:{}),...(breeze?{cfg_scale:cfg}:{})};
    await api('/v1/tts/generate?wait=false',{method:'POST',body:JSON.stringify(request)});submitted();
  });}
  return <div className="two-column"><section className="panel"><h2>{t('让文字说话')}</h2>
    <label>{t('语音模型')}<select value={model} onChange={e=>{setModel(e.target.value);setMode(e.target.value==='breeze-tts2'?'design':'preset');setLanguage('Chinese');setError('');}}><option value="qwen3-tts">Qwen3-TTS</option><option value="breeze-tts2">Breeze TTS 2</option></select></label>
    <label>{t('要朗读的文字')}<textarea rows={6} maxLength={2000} value={text} onChange={e=>setText(e.target.value)}/></label>
    <label>{t('语言')}<select value={language} onChange={e=>setLanguage(e.target.value)}>{(breeze?['Chinese','English','Auto']:['Chinese','English','Japanese','Korean','German','French','Russian','Portuguese','Spanish','Italian','Auto']).map(l=><option key={l} value={l}>{t(l)}</option>)}</select></label>
    <label>{t('目标音色')}<select value={mode} onChange={e=>setMode(e.target.value)}><option value={breeze?'design':'preset'}>{breeze?t('文字设计音色'):t('选择预设音色')}</option><option value="reference">{t('使用参考音频')}</option></select></label>
    {mode==='preset' && <label>{t('预设音色')}<select value={speaker} onChange={e=>setSpeaker(e.target.value)}>{voices.map(v=><option key={v.id} value={v.id}>{t(v.name)} · {t(v.description)}</option>)}</select></label>}
    {mode==='preset' && voices.find(v=>v.id===speaker)?.preview_url && <button className="button light" onClick={()=>media(voices.find(v=>v.id===speaker).preview_url,speaker+'.wav')}><PlaybackMark source={voices.find(v=>v.id===speaker).preview_url} size={16} label={t('试听此音色')}/></button>}
    {mode==='reference' && <><ReferenceMedia file={reference} onChange={setReference} disabled={busy} api={api} service="tts"/><p className="muted">{t('建议使用清晰、单人、无音乐的录音。')} 3–30 s</p><label>{breeze?t('参考音频对应文字（必填）'):t('参考音频对应文字（可选）')}<textarea value={referenceText} onChange={e=>setReferenceText(e.target.value)} rows={2}/></label></>}
    {(breeze||mode==='preset') && <label>{breeze?t('音色与表达指令'):t('表达方式（可选）')}<textarea rows={2} value={instruct} onChange={e=>setInstruct(e.target.value)} placeholder={t('例如：年轻温柔的女声，语速稍慢，带着笑意')}/></label>}
    {breeze && <label>{t('提示词引导系数')}<input type="number" min={0.1} max={20} step={0.1} value={cfg} onChange={e=>setCfg(Number(e.target.value))}/></label>}
    {error && <p role="alert" className="song-error">{error}</p>}
    {!ready && <p className="inline-note">{current?.message || t('服务尚未就绪')}</p>}
    <button className="button primary full" disabled={busy||!online||!ready||!text.trim()||(mode==='reference'&&(!reference||(breeze&&!referenceText.trim())))||(breeze&&mode==='design'&&!instruct.trim())} onClick={generate}><Play size={16}/>{t('生成语音')}</button>
  </section><section className="panel"><h2>{breeze?'Breeze TTS 2':'Qwen3-TTS'}</h2><p>{breeze?t('支持中英文、文字设计音色、参考音色克隆及情绪指令。'):t('支持中文等 10 种语言。预设涵盖明亮女声、温柔女声、醇厚男声、方言及外语音色，也可上传参考录音克隆音色。')}</p>
    <p className="muted">{t('两个模型共用 TTS 运行环境，任务完成后释放显存。')}</p>
    {breeze && <><p className="inline-note">{t('Breeze 模型及本地输出仅限非商业用途。官方支持 Linux，Windows 兼容性仍需模型实测。')}</p><button className="button light" disabled={busy||!online||download?.status==='running'} onClick={()=>action(async()=>{const d=await api('/internal/tts/breeze/download',{method:'POST'});setInfo((old:any)=>({...old,download:d}));})}><Download size={16}/>{t('下载 Breeze 模型')}</button>
    {download?.status==='running' && <><progress max={download.total||1} value={download.downloaded}/><p className="muted">{download.file} · {(download.downloaded/1024**3).toFixed(2)} / {(download.total/1024**3).toFixed(2)} GB</p><button className="text-button" onClick={()=>action(async()=>{await api('/internal/tts/breeze/download',{method:'DELETE'});})}>{t('取消下载')}</button></>}
    {download?.status==='succeeded' && <p>{t('模型下载完成，路径已保存；请重启文字转语音服务使配置生效。')}</p>}
    {download?.status==='failed' && <p role="alert" className="song-error">{download.error}</p>}
    {download?.status==='cancelled' && <p>{t('下载已取消，可重新点击下载。')}</p>}
    <p className="muted">{t('从 Hugging Face 官方仓库下载；已完成且校验通过的文件会复用。')}</p></>}
    <button className="button light" onClick={configure}><Settings2 size={16}/>{t('配置模型')}</button><p className="muted">{t('任务完成后可在任务记录中试听和下载。模型按需加载，任务结束释放显存。')}</p>
  </section></div>;
}

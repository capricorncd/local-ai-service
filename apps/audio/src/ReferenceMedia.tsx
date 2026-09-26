import {InfoTip} from './InfoTip';
import {ApiReadyContext} from './ApiReadyContext';
import {useContext, useEffect, useRef, useState} from 'react';
import {Upload, X} from 'lucide-react';
import {t} from './i18n';

type Api = (path: string, options?: RequestInit) => Promise<any>;
const uploads = new WeakMap<File, Promise<string>>();
export function uploadReference(file: File, api: Api) {
  let pending = uploads.get(file);
  if (!pending) {
    const body = new FormData(); body.append('file', file);
    pending = api('/v1/uploads', {method: 'POST', body}).then(r => r.upload_id as string);
    uploads.set(file, pending);
    pending.catch(() => uploads.delete(file));
  }
  return pending;
}

export function ReferenceMedia({file, onChange, disabled = false, api, service, label, help}: {
  file: File|null; onChange: (file: File|null) => void; disabled?: boolean;
  api: Api; service: 'music'|'tts'|'vc'|'auk'|'denoise'|'separation'; label?: string; help?: string;
}) {
  const apiReady = useContext(ApiReadyContext);
  const video = !!file && /\.(mp4|mov|mkv|webm|avi)$/i.test(file.name);
  const canPreview = !video || apiReady;
  const [retry,setRetry] = useState(0);
  const [dragging,setDragging] = useState(false);
  const [error,setError] = useState('');
  const [preview,setPreview] = useState('');
  const [loading,setLoading] = useState(false);
  const apiRef = useRef(api); apiRef.current = api;
  useEffect(() => {
    let cancelled = false, url = '';
    setPreview(''); setError(''); setLoading(!!file && canPreview);
    if (file && canPreview) (async () => {
      try {
        if (/\.(mp4|mov|mkv|webm|avi)$/i.test(file.name)) {
          const id = await uploadReference(file, apiRef.current);
          if (cancelled) return;
          const result = await apiRef.current(`/v1/uploads/${encodeURIComponent(id)}/audio-preview?service=${service}`, {method:'POST'});
          if (cancelled) return;
          const bytes = Uint8Array.from(atob(result.audio_base64), c => c.charCodeAt(0));
          url = URL.createObjectURL(new Blob([bytes], {type:'audio/wav'}));
        } else url = URL.createObjectURL(file);
        if (!cancelled) setPreview(url);
      } catch (e) { if (!cancelled) setError(String(e)); }
      finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [file,service,canPreview,retry]);
  function choose(files: FileList|null) {
    setDragging(false);
    if (disabled || !files?.length) return;
    if (files.length !== 1) {setError('一次请选择一个音频或视频文件'); return;}
    const next = files[0];
    if (!/\.(wav|mp3|flac|ogg|m4a|aac|opus|mp4|mov|mkv|webm|avi)$/i.test(next.name)) {setError('请选择支持的音频或视频文件'); return;}
    if (!next.size || next.size > 512*1024*1024) {setError('文件须非空且不超过 512 MB'); return;}
    setError(''); onChange(next);
  }
  return <section className="music-reference" aria-label={label||t('参考音频或视频')}>
    {label&&<p className="muted">{label}</p>}
    <label className={`dropzone ${dragging?'dragging':''}`} onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect=disabled?'none':'copy';if(!disabled)setDragging(true);}} onDragLeave={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setDragging(false);}} onDrop={e=>{e.preventDefault();e.stopPropagation();choose(e.dataTransfer.files);}}>
      <input type="file" accept=".wav,.mp3,.flac,.ogg,.m4a,.aac,.opus,.mp4,.mov,.mkv,.webm,.avi" aria-label={label||t('参考音频或视频')} disabled={disabled} onChange={e=>{choose(e.target.files);e.target.value='';}}/>
      <Upload size={22}/><strong>{file?.name || t('拖入音频或视频，或点击上传')}</strong>
      <p>{file ? `${(file.size/1024/1024).toFixed(1)} MB` : 'WAV / MP3 / FLAC / MP4 / MOV / MKV / WEBM / AVI · ≤ 512 MB'}</p>
    </label>
    {file && !canPreview && <p role="status">{t('等待 API 连接，连接后将自动准备预览。')}</p>}
    {loading && <p role="status">{t('正在准备音频预览…')}</p>}
    {file && <div className="reference-preview">{preview && <audio controls src={preview} onError={()=>setError('音频预览失败，可尝试其他格式')}/>}<button type="button" className="text-button" disabled={disabled} onClick={()=>onChange(null)}><X size={14}/>{t('移除参考音频')}</button></div>}
    <span className="reference-info"><InfoTip text={[service === 'music' && file && /\.(mp4|mov|mkv|webm|avi)$/i.test(file.name) ? t('最多试听 15 分钟，上传文件未截断；生成歌谱与歌曲改编使用完整音轨，最长 15 分钟。') : t('视频仅使用第一条音轨，最多试听 15 分钟；正式处理仍使用原文件及模型的时长限制。'), help].filter(Boolean).join('\n\n')}/></span>
    {error && <><p role="alert" className="song-error">{t(error)}</p>{file && <button type="button" className="button light" disabled={loading || !canPreview} onClick={()=>setRetry(value=>value+1)}>{t('重试预览')}</button>}</>}
  </section>;
}

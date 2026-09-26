import {useRef, useState} from 'react';
import {Check, Loader2, Pencil, X} from 'lucide-react';
import {t} from './i18n';

export function SongTitle({title, unplayed, disabled, save, onError, tag}: {
  title:string; unplayed:boolean; disabled:boolean; tag?:string;
  save:(title:string)=>Promise<void>; onError:(error:string)=>void;
}) {
  const [draft,setDraft]=useState<string|null>(null);
  const [saving,setSaving]=useState(false);
  const submitting=useRef(false);
  async function submit() {
    if(disabled||submitting.current||!draft?.trim())return;
    if(draft.trim()===title){setDraft(null);return;}
    submitting.current=true;setSaving(true);onError('');
    try{await save(draft.trim());setDraft(null);}catch(error){onError(String(error));}
    finally{submitting.current=false;setSaving(false);}
  }
  return <div className="song-title">{tag&&<span className={'song-tag song-title-tag'+(unplayed?' unplayed':'')} title={unplayed?t('尚未播放'):undefined} aria-label={unplayed?tag+' · '+t('尚未播放'):tag}>{tag}</span>}{draft===null?<><strong title={title}>{unplayed&&!tag&&<span className="unplayed-dot" role="img" aria-label={t('尚未播放')} title={t('尚未播放')}/>} {title}</strong><button type="button" className="song-title-icon" disabled={disabled} title={t('重命名')} aria-label={t('重命名')} onClick={()=>{setDraft(title);onError('');}}><Pencil size={14}/></button></>:<form className="song-title-form" onSubmit={e=>{e.preventDefault();void submit();}}><input autoFocus onFocus={e=>e.target.select()} aria-label={t('歌名')} value={draft} maxLength={120} disabled={saving} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.nativeEvent.isComposing||e.keyCode===229){if(e.key==='Enter')e.preventDefault();return;}if(e.key==='Escape'&&!saving){e.preventDefault();setDraft(null);}}}/><button type="submit" className="song-title-icon" disabled={disabled||saving||!draft.trim()} title={t('保存')} aria-label={t('保存')}>{saving?<Loader2 size={15} className="spin"/>:<Check size={15}/>}</button><button type="button" className="song-title-icon" disabled={saving} title={t('取消')} aria-label={t('取消')} onClick={()=>setDraft(null)}><X size={15}/></button></form>}</div>;
}

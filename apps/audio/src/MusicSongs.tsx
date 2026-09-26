import {type PlaybackTrack} from './playbackQueue';
import {SongFilters} from './SongFilters';
import {SongMoveMenu} from './SongMoveMenu';
import {SongTitle} from './SongTitle';
import {SongMoreMenu} from './SongMoreMenu';
import {RevealFileButton} from './RevealFileButton';
import {PlaybackMark} from './PlaybackMark';
import {t, locale, useLanguage, LanguageSettings, serviceMessage} from './i18n';
import { useEffect, useState } from 'react';
import { Copy, Star, Heart, Folder, Plus, Search, ChevronRight, Download, ListMusic, Play, Loader2, Mic2, Shuffle, Pencil, FilePenLine, Split, Trash2 } from 'lucide-react';
export type SongJob = {
    song_annotations?: Record<string,{rating:number;favorite:boolean}>;
    played_indices?: number[];
    song_metadata?: Record<string, {
        title: string;
        group: string;
    }>;
    id: string;
    service: string;
    status: string;
    created: number;
    error: string | null;
    request: Record<string, unknown>;
    result: {
        scores?: {
            url: string;
            path?: string;
            audio_index: number;
        }[];
        files: {
            url: string;
            path: string;
            title?: string;
            tag?: string;
            duration: number;
        }[];
    } | null;
};
function formatDuration(seconds: number) {
    if (!Number.isFinite(seconds) || seconds < 0) return '—';
    const milliseconds = Math.round(seconds * 1000);
    const minutes = Math.floor(milliseconds / 60000);
    const remainder = Math.floor(milliseconds / 1000) % 60;
    return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}.${String(milliseconds % 1000).padStart(3, '0')}`;
}

export function MusicSongs({ jobs, media, save, reuse, separate, remove, disabled, online, api, workspace, setWorkspace, annotated, previewScore }: {
    previewScore: (url:string)=>void;
    remove: (job: SongJob) => Promise<void>;
    online: boolean;
    annotated: (jobId:string,index:number,value:{rating:number;favorite:boolean})=>void;
    workspace: string|null;
    setWorkspace: (name: string|null)=>void;
    api: (path: string, options?: RequestInit) => Promise<any>;
    separate: (job: SongJob, index: number) => Promise<void>;
    disabled: boolean;
    reuse: (job: SongJob, index: number, title: string, action: 'cover' | 'remix' | 'score' | 'lyrics' | 'reuse') => void;
    save: (id: string, index: number, title: string, group: string) => Promise<void>;
    jobs: SongJob[];
    media: (url: string, name: string, download?: boolean, queue?:PlaybackTrack[]) => Promise<void>;
}) {
    const [workspaceNames,setWorkspaceNames]=useState<string[]>([]);
    const [search,setSearch]=useState('');
    const [songSearch,setSongSearch]=useState('');
    const songTitle=(job:SongJob,index:number)=>job.song_metadata?.[String(index)]?.title||job.result?.files[index]?.title||(job.request.song_titles as string[]|undefined)?.[index]||String(job.request.title||t('歌曲 {0}_{1}',job.id.slice(0,8),index+1));
    const matchesSearch=(job:SongJob,index:number)=>`${songTitle(job,index)} ${String(job.request.style||'')}`.toLocaleLowerCase().includes(songSearch.trim().toLocaleLowerCase());
    const [creating,setCreating]=useState(false);
    const [newName,setNewName]=useState('');
    const [workspaceError,setWorkspaceError]=useState('');
    useEffect(()=>{if(!online){setWorkspaceError('');return;}let cancelled=false;api('/v1/music/workspaces').then(names=>{if(!cancelled){setWorkspaceNames(names);setWorkspaceError('');}}).catch(e=>{if(!cancelled)setWorkspaceError(String(e));});return()=>{cancelled=true;};},[online]);
    const [tagFilter,setTagFilter]=useState('*');
    const [ratingFilter,setRatingFilter]=useState('*');
    const [favoritesOnly,setFavoritesOnly]=useState(false);
    const [scoresOnly,setScoresOnly]=useState(false);
    const [annotationBusy,setAnnotationBusy]=useState(false);
    const matchesAnnotation=(value?:{rating:number;favorite:boolean})=>(ratingFilter==='*'||(value?.rating||0)===Number(ratingFilter))&&(!favoritesOnly||!!value?.favorite);
    async function setAnnotation(jobId:string,index:number,rating:number,favorite:boolean){
        if(annotationBusy)return;
        setAnnotationBusy(true);setError('');
        try{const result=await api(`/v1/music/jobs/${jobId}/songs/${index}/annotation`,{method:'PUT',body:JSON.stringify({rating,favorite})});annotated(jobId,index,result);}
        catch(e){setError(String(e));}finally{setAnnotationBusy(false);}
    }
    const [deleting,setDeleting]=useState('');
    const [separating,setSeparating]=useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const groups = [...new Set([...workspaceNames, ...jobs.flatMap(j => [...Object.values(j.song_metadata || {}).map(m => m.group), String(j.request.source_group || '')]).filter(Boolean)])].sort();
    const music = jobs.filter(j => j.service === 'music' && j.request.operation !== 'transcribe');
    const labels: Record<string, string> = { queued: t("排队中"), running: t("生成中"), succeeded: t("已生成"), failed: t("生成失败"), cancelled: t("已取消") };
    const tracks = music.flatMap(job=>Array.from({length:job.result?.files.length||Number(job.request.count)||1},(_,index)=>({
        file:job.result?.files[index],
        hasScore:!!job.result?.scores?.some(score=>score.audio_index===index),
        title:songTitle(job,index),
        matchesSearch:matchesSearch(job,index),
        annotation:job.song_annotations?.[String(index)],
        group:job.song_metadata?.[String(index)]?.group ?? String(job.request.source_group||''),
        tag:job.request.operation==='separate'?(job.result?.files[index]?.tag||(index===0?'vocals':'instrumental')):'original'
    })));
    const visibleCount=tracks.filter(track=>track.matchesSearch&&(!scoresOnly||track.hasScore)&&track.group===workspace&&(tagFilter==='*'||track.tag===tagFilter)&&matchesAnnotation(track.annotation)).length;
    const playbackQueue=tracks.filter(track=>track.file&&track.matchesSearch&&(!scoresOnly||track.hasScore)&&track.group===workspace&&(tagFilter==='*'||track.tag===tagFilter)&&matchesAnnotation(track.annotation)).map(track=>({url:track.file!.url,name:track.title}));
    function openWorkspace(name:string|null){setWorkspace(name);setSongSearch('');setError('');setTagFilter('*');setRatingFilter('*');setFavoritesOnly(false);setScoresOnly(false);setCreating(false);}
    return <section className="panel music-song-panel"><div className="section-title"><div className="workspace-breadcrumb" role="navigation" aria-label="Workspaces"><button type="button" onClick={()=>openWorkspace(null)} aria-current={workspace===null?'page':undefined}>Workspaces</button>{workspace!==null&&<><ChevronRight size={16}/><strong>{workspace||t('未分组')}</strong></>}</div><span className="muted">{workspace===null?t('工作区数量：{0}',groups.length+1):t('{0} 首 / 音轨',visibleCount)}</span></div>
    {(error||workspaceError)&&<p className="song-error" role="alert">{error||workspaceError}</p>}
    {workspace===null?<><div className="search workspace-search"><Search size={16}/><input aria-label={t('搜索工作区')} placeholder={t('搜索工作区')} value={search} onChange={e=>setSearch(e.target.value)}/></div>
      <div className="workspace-list"><button type="button" className="workspace-row workspace-create" disabled={disabled} onClick={()=>{setCreating(true);setNewName('');setError('');}}><span className="workspace-art"><Plus size={26}/></span><strong>{t('创建工作区')}</strong></button>
      {creating&&<form className="workspace-create-form" onSubmit={async e=>{e.preventDefault();if(!newName.trim()||saving)return;setSaving(true);setError('');try{const result=await api('/v1/music/workspaces',{method:'POST',body:JSON.stringify({name:newName.trim()})});setWorkspaceNames(names=>[...new Set([...names,result.name])]);openWorkspace(result.name);}catch(e){setError(String(e));}finally{setSaving(false);}}}><input autoFocus aria-label={t('工作区名称')} placeholder={t('工作区名称')} maxLength={60} value={newName} onChange={e=>setNewName(e.target.value)} disabled={saving}/><div className="actions"><button className="button primary" disabled={saving||disabled||!newName.trim()}>{t('创建工作区')}</button><button type="button" className="button light" disabled={saving} onClick={()=>setCreating(false)}>{t('取消')}</button></div></form>}
      {['',...groups].filter(name=>(name||t('未分组')).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())).map((name,index)=><button type="button" className="workspace-row" key={name} onClick={()=>openWorkspace(name)}><span className={'workspace-art workspace-color-'+index%5}><Folder size={25}/></span><span><strong>{name||t('未分组')}</strong><small>{t('{0} 首 / 音轨',tracks.filter(track=>track.group===name).length)}</small></span><ChevronRight size={16}/></button>)}
      </div><p className="muted">{t('歌曲统计与列表显示最近 200 条任务中的音轨。')}</p></>:<><SongFilters query={songSearch} setQuery={setSongSearch} tag={tagFilter} setTag={setTagFilter} rating={ratingFilter} setRating={setRatingFilter} favorites={favoritesOnly} setFavorites={setFavoritesOnly} scores={scoresOnly} setScores={setScoresOnly}/ >{!visibleCount&&<div className="empty"><Folder size={28}/><p>{t('此工作区暂无符合条件的歌曲')}</p><p>{t('可通过歌曲的“移动至”将作品移入工作区。')}</p></div>}<div className="music-song-list">{music.flatMap(job => Array.from({ length: job.result?.files.length || Number(job.request.count) || 1 }, (_, index) => {
            const file = job.result?.files[index];
            const annotation=job.song_annotations?.[String(index)]||{rating:0,favorite:false};
            if(!matchesAnnotation(annotation)||!matchesSearch(job,index))return null;
            const titles = job.request.song_titles as string[] | undefined;
            const meta = job.song_metadata?.[String(index)];
            const group = meta?.group ?? String(job.request.source_group || '');
            const isStem=job.request.operation==='separate';
            const tag=isStem?(file?.tag || (index===0?'vocals':'instrumental')):'original';
            if(tagFilter!=='*' && tagFilter!==tag)return null;
            const pending=jobs.some(j=>j.request.operation==='separate'&&j.request.source_job_id===job.id&&j.request.source_audio_index===index&&['running','queued'].includes(j.status));
            if (group !== workspace)
                return null;
            const title = songTitle(job,index);
            const score = job.result?.scores?.find(item=>item.audio_index===index);
            if(scoresOnly&&!score)return null;
            return <article className="music-song" key={`${job.id}-${index}`}><div className="music-song-heading"><SongTitle title={title} unplayed={!!file&&!job.played_indices?.includes(index)} disabled={disabled||saving} save={name=>save(job.id,index,name,group)} onError={setError}/>{job.status==='succeeded'?<SongMoreMenu>{!isStem && <><button role="menuitem" className="button light" title={t("从原音频提取旋律，换风格生成翻唱版本")} disabled={!file} onClick={() => reuse(job, index, title, 'cover')}><Mic2 size={14}/>Cover</button><button role="menuitem" className="button light" title={t("从原音频提取旋律与和弦，修改风格进行改编")} disabled={!file} onClick={() => reuse(job, index, title, 'remix')}><Shuffle size={14}/>Remix</button><button role="menuitem" className="button light" disabled={!file || !job.result?.scores?.some(s => s.audio_index === index)} title={t("编辑已保存的旋律、节奏与和弦")} onClick={() => reuse(job, index, title, 'score')}><Pencil size={14}/>{t("改曲")}</button><button role="menuitem" className="button light" disabled={!file} onClick={() => reuse(job, index, title, 'lyrics')}><FilePenLine size={14}/>{t("改词")}</button><button role="menuitem" className="text-button" onClick={() => reuse(job, index, title, 'reuse')}><Copy size={14}/>{t("复用参数")}</button><button role="menuitem" className="button light" disabled={disabled || !file || job.status!=='succeeded' || pending || !!separating} onClick={async()=>{setSeparating(job.id+':'+index);setError('');try{await separate(job,index);}catch(e){setError(String(e));}finally{setSeparating('');}}}><Split size={14}/>{pending?t('分离中'):t('人声分离')}</button></>}<SongMoveMenu groups={groups} current={group} disabled={disabled||saving} move={async target=>{setSaving(true);setError('');try{await save(job.id,index,title,target);}catch(e){setError(String(e));}finally{setSaving(false);}}}/><button type="button" role="menuitem" className="button light song-trash" title={t('将本次生成的整个目录移入回收站，包含同批次所有歌曲、歌谱和其他文件。')} disabled={disabled || !!deleting || saving} onClick={async()=>{setDeleting(job.id);setError('');try{await remove(job);}catch(e){setError(String(e));}finally{setDeleting('');}}}><Trash2 size={14}/>{t('删除整个生成目录')}</button></SongMoreMenu>:<span className={`song-state ${job.status}`}>{['running', 'queued'].includes(job.status) && <Loader2 size={12} className={job.status === 'running' ? 'spin' : ''}/>} {isStem && job.status==='running' ? t('分离中') : labels[job.status] || job.status}</span>}</div>{file&&<div className="song-annotations"><div className="song-stars" role="group" aria-label={t('歌曲评分')}>{[1,2,3,4,5].map(n=><button type="button" key={n} className={n<=annotation.rating?'rated':''} disabled={disabled||annotationBusy} aria-label={annotation.rating===n?t('清除评分'):t('评为 {0} 星',n)} title={annotation.rating===n?t('清除评分'):t('评为 {0} 星',n)} onClick={()=>setAnnotation(job.id,index,annotation.rating===n?0:n,annotation.favorite)}><Star size={17} fill={n<=annotation.rating?'currentColor':'none'}/></button>)}</div><button type="button" className={'song-favorite '+(annotation.favorite?'favorited':'')} disabled={disabled||annotationBusy} aria-pressed={annotation.favorite} onClick={()=>setAnnotation(job.id,index,annotation.rating,!annotation.favorite)}><Heart size={16} fill={annotation.favorite?'currentColor':'none'}/>{annotation.favorite?t('已收藏'):t('收藏')}</button></div>}<div className="song-tags"><span className={'song-tag '+tag}>{t(tag==='vocals'?'人声':tag==='instrumental'?'伴奏':'原曲')}</span>{isStem && <span className="muted">{t('来源：{0}',String(job.request.source_title || ''))}</span>}</div><p className="muted">{group || t("未分组")} · {new Date(job.created * 1000).toLocaleString(locale())}{file ? ` · ${formatDuration(file.duration)}` : ''}</p>{job.error && <p className="song-error" title={job.error}>{job.error}</p>}{file && <div className="actions"><button className="button light" onClick={() => media(file.url, title, false, playbackQueue)}><PlaybackMark source={file.url} label={t("播放")}/></button><button className="button light" onClick={() => media(file.url, `${title.replace(/[<>:"/\\|?*]/g, '_')}.wav`, true)}><Download size={14}/>{t("下载")}</button><RevealFileButton path={file.path}/>{score && <SongMoreMenu label={t('歌谱')} icon={<ListMusic size={14}/>}><button type="button" role="menuitem" className="button light" onClick={()=>previewScore(score.url)}><ListMusic size={14}/>{t('预览')}</button><button type="button" role="menuitem" className="button light" onClick={()=>media(score.url+'?download=true',`${title.replace(/[<>:"/\\|?*]/g,'_')}.abc`,true).catch(error=>setError(String(error)))}><Download size={14}/>{t('下载')}</button><RevealFileButton path={score.path}/></SongMoreMenu>}</div>}</article>;
        }))}</div></>}</section>;
}

import {ApiReadyContext} from './ApiReadyContext';
import {AppearanceSettings,initializeTheme} from '../../../packages/ui/src/index';
import {installExclusivePlayback, pauseOtherAudio} from './exclusivePlayback';
import {nextTrack,type PlaybackMode,type PlaybackTrack} from './playbackQueue';
import {useDraft, useDraftFile} from './useDraft';
import {MusicPresets} from './MusicPresets';
import {ReferenceMedia, uploadReference} from './ReferenceMedia';
import {RevealFileButton} from './RevealFileButton';
import {PlaybackContext, PlaybackLoadingContext, PlaybackMark} from './PlaybackMark';
import {TtsPanel} from './TtsPanel';
import {MusicReference} from './MusicReference';
import {t, locale, useLanguage, LanguageSettings, serviceMessage} from './i18n';
import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { invoke, isTauri } from '@tauri-apps/api/core';
import { open, save } from '@tauri-apps/plugin-dialog';
import { ArrowRight, Repeat1, Repeat, Mic, Speech, AudioLines, LayoutDashboard, Music2, Waves, Users, LibraryBig, Settings2, Terminal, ArrowUpRight, RefreshCw, Play, Square, Save, Check, Circle, ChevronRight, Cpu, Server, FolderOpen, Search, Download, KeyRound, Copy, Plus, Clock3, FileAudio, AlertCircle, X, Loader2, Cable, Upload, ListMusic } from 'lucide-react';
import './style.css';
import { MusicLora, noLora } from './MusicLora';
import { MusicScores, type Score } from './MusicScores';
import { MusicSongs, type SongJob } from './MusicSongs';
import { AukEditor } from './AukEditor';
type ServiceName = 'music' | 'denoise' | 'separation' | 'sfx' | 'tts' | 'vc' | 'auk' | 'library';
type Page = 'overview' | ServiceName | 'jobs' | 'api' | 'logs' | 'settings';
type Config = Record<ServiceName, Record<string, string | number | boolean>>;
type ServiceState = {
    status: string;
    message: string;
    pending_restart: boolean;
    busy: boolean;
};
type Status = {
    services: Record<ServiceName, ServiceState>;
    current_job: {
        id: string;
        service: string;
    } | null;
    queued: number;
};
type ResultFile = {
    tag?: string;
    title?: string;
    path: string;
    url: string;
    duration: number;
    sample_rate: number;
    seed?: number;
    speaker?: number;
};
type Job = {
    song_annotations?: Record<string,{rating:number;favorite:boolean}>;
    played_indices?: number[];
    song_metadata?: Record<string, {
        title: string;
        group: string;
    }>;
    id: string;
    service: ServiceName;
    status: string;
    created: number;
    error: string | null;
    result: {
        files: ResultFile[];
        scores?: Score[];
    } | null;
    request: Record<string, unknown>;
};
type Sound = {
    id: string;
    name: string;
    category: string;
    size: number;
    url: string;
};
type Connection = {
    base: string;
    token: string;
    data_dir?: string;
    desktop_key?: string;
};
function App() {
    useLanguage();
    const names: Record<ServiceName, string> = { music: t("音乐生成"), denoise: t("音频降噪"), separation: t("人声分离"), sfx: t("音效生成"), tts: t("文字转语音"), vc: t("音色转换"), auk: t("音频编辑"), library: t("音效资源库") };
    const icons = { music: Music2, denoise: Waves, separation: Users, sfx: AudioLines, tts: Speech, vc: Mic, auk: AudioLines, library: LibraryBig };
    const statuses: Record<string, string> = { ready: t("已就绪"), needs_config: t("待配置"), stopped: t("已停用"), checking: t("检查中"), queued: t("排队中"), running: t("处理中"), succeeded: t("已完成"), failed: t("失败"), cancelled: t("已取消") };
    const nav: {
        id: Page;
        label: string;
        icon: typeof AudioLines;
    }[] = [{ id: 'overview', label: t("服务概览"), icon: LayoutDashboard }, { id: 'music', label: t("音乐生成"), icon: Music2 }, { id: 'denoise', label: t("音频降噪"), icon: Waves }, { id: 'separation', label: t("人声分离"), icon: Users }, { id: 'sfx', label: t("音效生成"), icon: AudioLines }, { id: 'tts', label: t("文字转语音"), icon: Speech }, { id: 'vc', label: t("音色转换"), icon: Mic }, { id: 'auk', label: t("音频编辑"), icon: AudioLines }, { id: 'library', label: t("音效资源库"), icon: LibraryBig }, { id: 'jobs', label: t("任务记录"), icon: ListMusic }, { id: 'api', label: t("API 接入"), icon: Cable }, { id: 'logs', label: t("运行日志"), icon: Terminal }, { id: 'settings', label: t("应用设置"), icon: Settings2 }];
    const languages = [['Chinese', t("中文")], ['Auto', t("自动")], ['English', t("英语")], ['Japanese', t("日语")], ['Korean', t("韩语")], ['German', t("德语")], ['French', t("法语")], ['Russian', t("俄语")], ['Portuguese', t("葡萄牙语")], ['Spanish', t("西班牙语")], ['Italian', t("意大利语")]];
    const [lora, setLora] = useDraft('main.tsx:lora', noLora);
    const [generateScore, setGenerateScore] = useDraft('main.tsx:generateScore', false);
    const [songTitle, setSongTitle] = useDraft('main.tsx:songTitle', '');
    const [musicWorkspace,setMusicWorkspace]=useDraft<string|null>('main.tsx:musicWorkspace', '', value=>value===null||typeof value==='string');
    const [musicMinutes,setMusicMinutes] = useDraft('main.tsx:musicMinutes', '');
    const savedVocalLyrics = useRef('');
    const musicStyleRef = useRef<HTMLTextAreaElement>(null);
    const [variation, setVariation] = useDraft<{
        job_id: string;
        audio_index: number;
        title: string;
        reference: 'audio' | 'score';
        action: string;
    } | null>('main.tsx:variation', null);
    const [variationAbc, setVariationAbc] = useDraft('main.tsx:variationAbc', '');
    const [musicReference, setMusicReference] = useDraftFile('main.tsx:musicReference');
    const lyricsRef = useRef<HTMLTextAreaElement>(null);
    const [page, setPage] = useDraft<Page>('main.tsx:page', 'overview', value=>nav.some(item=>item.id===value));
    const [conn, setConn] = useState<Connection | null>(null);
    const connRef = useRef<Connection | null>(null);
    const [status, setStatus] = useState<Status | null>(null);
    const [config, setConfig] = useState<Config | null>(null);
    const [jobs, setJobs] = useState<Job[]>([]);
    const [error, setError] = useState('');
    const [toast, setToast] = useState('');
    const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    useEffect(() => () => { if (toastTimer.current !== null) clearTimeout(toastTimer.current); }, []);
    const [busy, setBusy] = useState('');
    const [online, setOnline] = useState(false);
    const [editing, setEditing] = useState<ServiceName | null>(null);
    const [sounds, setSounds] = useState<Sound[]>([]);
    const [total, setTotal] = useState(0);
    const [offset, setOffset] = useState(0);
    const [categories, setCategories] = useState<{
        category: string;
        count: number;
    }[]>([]);
    const [q, setQ] = useDraft('main.tsx:q', '');
    const [category, setCategory] = useDraft('main.tsx:category', '');
    const [logs, setLogs] = useState<string[]>([]);
    const [lyrics, setLyrics] = useDraft('main.tsx:lyrics', '');
    const [style, setStyle] = useDraft('main.tsx:style', '');
    const [count, setCount] = useDraft('main.tsx:count', 1);
    const [seed, setSeed] = useDraft('main.tsx:seed', 42);
    const [mode, setMode] = useDraft('main.tsx:mode', 'full');
    const [sfxPrompt, setSfxPrompt] = useDraft('main.tsx:sfxPrompt', '雨水轻轻落在树叶上，远处偶尔传来鸟鸣，没有音乐和说话声');
    const [sfxSeconds, setSfxSeconds] = useDraft('main.tsx:sfxSeconds', '');
    const [sfxCount, setSfxCount] = useDraft('main.tsx:sfxCount', '');
    const [voices, setVoices] = useState<{
        id: string;
        name: string;
        description: string;
        vc_available: boolean;
        preview_url: string | null;
    }[]>([]);
    const [voiceMode, setVoiceMode] = useDraft('main.tsx:voiceMode', 'preset');
    const [selectedVoice, setSelectedVoice] = useDraft('main.tsx:selectedVoice', 'vivian');
    const [voiceReference, setVoiceReference] = useDraftFile('main.tsx:voiceReference');
    const [voiceSource, setVoiceSource] = useDraftFile('main.tsx:voiceSource');
    const [ttsText, setTtsText] = useDraft('main.tsx:ttsText', '你好，欢迎使用本地语音服务。让每一段文字，都拥有自然生动的声音。');
    const [ttsLanguage, setTtsLanguage] = useDraft('main.tsx:ttsLanguage', 'Chinese');
    const [referenceText, setReferenceText] = useDraft('main.tsx:referenceText', '');
    const [ttsInstruct, setTtsInstruct] = useDraft('main.tsx:ttsInstruct', '');
    const [separationMode,setSeparationMode]=useDraft('separation:mode','speakers');
    const [upload, setUpload] = useDraftFile('main.tsx:upload');
    const [playbackMode,setPlaybackMode]=useDraft<PlaybackMode>('playback:mode','sequence',value=>['sequence','single','list'].includes(String(value)));
    const playbackQueue=useRef<PlaybackTrack[]>([]);
    const audioRef=useRef<HTMLAudioElement>(null);
    const playbackRequest=useRef<AbortController|null>(null);
    const [loadingAudio,setLoadingAudio]=useState<string|null>(null);
    const [playingUrl,setPlayingUrl]=useState<string|null>(null);
    const [player, setPlayer] = useState<{
        source: string;
        url: string;
        name: string;
    } | null>(null);
    const [bootstrap, setBootstrap] = useState({ python: '', port: 19876 });
    const [tokenVisible, setTokenVisible] = useState(false);
    const [browserToken, setBrowserToken] = useState(sessionStorage.getItem('local-ai-token') || '');
    const [dirty, setDirty] = useState(false);
    const active = nav.find(n => n.id === page)!;
    function dismissToast() {
        if (toastTimer.current !== null) clearTimeout(toastTimer.current);
        toastTimer.current = null;
        setToast('');
    }
    function notify(text: string) {
        if (toastTimer.current !== null) clearTimeout(toastTimer.current);
        setToast(text);
        toastTimer.current = setTimeout(dismissToast, 5000);
    }
    useEffect(() => {
        const onFailure = () => notify(t('表单草稿保存或恢复失败，请检查本地存储空间。'));
        window.addEventListener('draft-save-failed', onFailure);
        return () => window.removeEventListener('draft-save-failed', onFailure);
    }, []);
    async function api(path: string, options: RequestInit = {}) {
        let c = connRef.current;
        const internal = path.startsWith('/internal/');
        if (internal && isTauri()) {
            c = await invoke<Connection>('connection');
            connRef.current = c;
            setConn(c);
        }
        if (!c)
            throw Error(t("API 服务尚未连接"));
        const response = await fetch(c.base + path, { ...options, headers: { Authorization: `Bearer ${c.token}`, ...(!(options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}), ...options.headers, ...(internal && isTauri() ? {'X-Desktop-Key': c.desktop_key || ''} : {}) } });
        if (!response.ok) {
            const data = await response.json().catch(() => ({ detail: response.statusText }));
            throw Error(typeof data.detail === 'string' ? serviceMessage(data.detail) : JSON.stringify(data.detail || data));
        }
        return response.json();
    }
    async function connectService() {
        try {
            const c = isTauri() ? await invoke<Connection>('connection') : { base: 'http://127.0.0.1:19876', token: sessionStorage.getItem('local-ai-token') || '' };
            connRef.current = c;
            setConn(c);
            const [s, cfg, j] = await Promise.all([api('/v1/status'), api('/v1/config'), api('/v1/jobs')]);
            setStatus(s);
            setConfig(cfg);
            setJobs(j);
            setOnline(true);
            setError('');
        }
        catch (e) {
            setOnline(false);
            setError(String(e));
        }
    }
    useEffect(() => { connectService(); if (isTauri())
        invoke<typeof bootstrap>('bootstrap').then(setBootstrap).catch(e => setError(String(e))); }, []);
    useEffect(() => { let running = false; const timer = setInterval(async () => { if (running)
        return; running = true; try {
        if (!connRef.current) {
            await connectService();
            return;
        }
        const [s, j] = await Promise.all([api('/v1/status'), api('/v1/jobs')]);
        setStatus(old=>JSON.stringify(old)===JSON.stringify(s)?old:s);
        setJobs(old=>JSON.stringify(old)===JSON.stringify(j)?old:j);
        setOnline(true);
        setError('');
        if (!config)
            setConfig(await api('/v1/config'));
    }
    catch (e) {
        setOnline(false);
        setError(String(e));
    }
    finally {
        running = false;
    } }, 2500); return () => clearInterval(timer); }, [config]);
    useEffect(() => { if (online)
        api('/v1/voices').then(setVoices).catch(e => notify(String(e))); }, [online, page]);
    async function uploadVoice(file: File) { return uploadReference(file, api); }
    async function submitVoice() {
        await act('voice', async () => {
            const reference = voiceMode === 'reference' && voiceReference ? await uploadVoice(voiceReference) : null;
            let params: Record<string, unknown>;
            if (page === 'tts')
                params = { text: ttsText, language: ttsLanguage, seed, ...(reference ? { reference_upload_id: reference, reference_text: referenceText } : { speaker: selectedVoice, instruct: ttsInstruct }) };
            else {
                if (!voiceSource)
                    throw Error(t("请选择原音频"));
                params = { source_upload_id: await uploadVoice(voiceSource), seed, ...(reference ? { reference_upload_id: reference } : { target_voice: selectedVoice }) };
            }
            await api(page === 'tts' ? '/v1/tts/generate?wait=false' : '/v1/voice/convert?wait=false', { method: 'POST', body: JSON.stringify(params) });
            setJobs(await api('/v1/jobs'));
            setPage('jobs');
            notify(t("任务已提交"));
        });
    }
    async function reuseSong(job: SongJob, index: number, title: string, action: 'cover' | 'remix' | 'score' | 'lyrics' | 'reuse') {
        const r = job.request;
        setBusy('load-song');
        try {
            const score = job.result?.scores?.find(s => s.audio_index === index);
            let abc = '';
            if ((action === 'score' || action === 'lyrics') && score)
                abc = (await api(score.url)).abc;
            setMusicReference(null);
            setSongTitle(title.slice(0, 120));
            setLyrics(String(r.lyrics || ''));
            setStyle(String(r.style || ''));
            setMusicMinutes(r.max_duration ? String(Number(r.max_duration)/60) : '');
            setCount(1);
            setSeed(Math.min(4294967294, Number(r.seed ?? 42) + index));
            const plan = action === 'cover' ? 'melody' : action === 'reuse' && ['full', 'melody', 'off'].includes(String(r.mode)) ? String(r.mode) : 'full';
            setMode(plan);
            setGenerateScore(action === 'reuse' ? plan !== 'off' && r.generate_score === true : true);
            const acoustic = typeof r.acoustic_lora === 'string' ? r.acoustic_lora : null;
            const planner = action === 'reuse' && typeof r.planner_lora === 'string' ? r.planner_lora : null;
            setLora({ lora_provider: acoustic || planner ? String(r.lora_provider || 'none') : 'none', acoustic_lora: acoustic, planner_lora: planner, acoustic_strength: Number(r.acoustic_strength ?? 1), planner_strength: Number(r.planner_strength ?? 1) });
            setVariation(action === 'reuse' ? null : { job_id: job.id, audio_index: index, title, reference: abc ? 'score' : 'audio', action });
            setVariationAbc(abc);
            notify(action === 'reuse' ? t("已回填参数，可修改后重新生成。") : action === 'cover' ? t("提取原音频旋律，以新风格翻唱；不保留原歌声音色。") : action === 'remix' ? t("参考原音频的旋律与和弦，重新演绎编曲和风格。") : action === 'lyrics' ? t("修改下方歌词后生成新版本。字数和节奏越接近原词，越容易匹配旋律；其他声音也可能变化。") : t("编辑下方 ABC，修改旋律、节奏或和弦后生成新版本。"));
            const field = action === 'lyrics' ? lyricsRef.current : musicStyleRef.current;
            field?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            field?.focus({ preventScroll: true });
        }
        catch (e) {
            notify(String(e));
        }
        finally {
            setBusy('');
        }
    }
    async function trashMusicJob(job: SongJob) {
        const sources = new Set((job.result?.files || []).map(file => file.url));
        if ((player && sources.has(player.source)) || (loadingAudio && sources.has(loadingAudio))) {
            playbackRequest.current?.abort();
            const audio = audioRef.current;
            if (audio) {
                audio.pause();
                audio.removeAttribute('src');
                audio.load(); // Cancel the media request before asking Windows to move the folder.
            }
            if (player) URL.revokeObjectURL(player.url);
            setPlayer(null);setPlayingUrl(null);setLoadingAudio(null);
        }
        playbackQueue.current = playbackQueue.current.filter(track => !sources.has(track.url));
        await api(`/internal/music/jobs/${job.id}`, {method:'DELETE'});
        setJobs(current => current.filter(item => item.id !== job.id));
        if (variation?.job_id === job.id) {setVariation(null);setVariationAbc('');}
        notify(t('整个生成目录已移入回收站，包含本次生成的所有歌曲和相关文件。'));
    }
    async function transcribeReference() {
        if (!musicReference) return;
        const upload_id = await uploadVoice(musicReference);
        await api('/internal/music/transcribe', { method: 'POST', body: JSON.stringify({
            upload_id, workspace: musicWorkspace || '', title: songTitle.trim() || musicReference.name.replace(/\.[^.]+$/, '').slice(0, 120),
            mode: mode === 'melody' ? 'melody' : 'full'
        }) });
        setJobs(await api('/v1/jobs'));
        notify(t('歌谱已加入生成队列，完成后可在下方预览和下载。'));
    }
    async function generateMusic() {
        if ((variation || musicReference) && lora.planner_lora) throw new Error(t('参考歌曲不使用规划 LoRA，请取消选择'));
        if (musicMinutes && (!Number.isFinite(Number(musicMinutes)) || Number(musicMinutes)<.1 || Number(musicMinutes)>15)) throw new Error(t('目标时长需在 0.1–15 分钟之间'));
        const music = { workspace: musicWorkspace || '', title: songTitle, lyrics, style, count, seed, mode, generate_score: generateScore, ...lora, ...(musicMinutes ? {max_duration:Number(musicMinutes)*60} : {}) };
        if (musicReference) {
            if (!isTauri()) throw new Error(t("歌曲改编仅限桌面应用使用"));
            const upload_id = await uploadVoice(musicReference);
            await api('/internal/music/reference', { method: 'POST', body: JSON.stringify({upload_id, music}) });
        }
        else if (variation) {
            if (!isTauri())
                throw new Error(t("歌曲改编仅限桌面应用使用"));
            await api('/internal/music/variation', { method: 'POST', body: JSON.stringify({ job_id: variation.job_id, audio_index: variation.audio_index, reference: variation.reference, music, ...(variation.reference === 'score' ? { abc: variationAbc } : {}) }) });
        }
        else
            await api('/v1/music/generate?wait=false', { method: 'POST', body: JSON.stringify(music) });
        setJobs(await api('/v1/jobs'));
        notify(t("歌曲已加入生成队列"));
    }
    async function act(id: string, fn: () => Promise<void>) { setBusy(id); try {
        await fn();
    }
    catch (e) {
        notify(String(e));
    }
    finally {
        setBusy('');
    } }
    async function restart(name: ServiceName) { await act('restart-' + name, async () => { await api(`/v1/services/${name}/restart`, { method: 'POST' }); setStatus(await api('/v1/status')); notify(t("{0}配置已重新检查", names[name])); }); }
    async function saveConfig() { if (!config)
        return; await act('save', async () => { await api('/v1/config', { method: 'PUT', body: JSON.stringify(config) }); setDirty(false); setStatus(await api('/v1/status')); notify(t("已保存，点击对应服务的重启按钮生效")); }); }
    async function loadSounds() { const [s, c] = await Promise.all([api(`/v1/sounds?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}&offset=${offset}`), api('/v1/categories')]); setSounds(s.items); setTotal(s.total); setCategories(c); }
    useEffect(() => { if (page === 'library' && online && status?.services.library.status === 'ready') {
        const t = setTimeout(() => { loadSounds().catch(e => notify(String(e))); }, 250);
        return () => clearTimeout(t);
    } }, [page, q, category, offset, online, status?.services.library.status]);
    useEffect(() => { if (page === 'logs' && online)
        api('/v1/logs').then(setLogs).catch(e => notify(String(e))); }, [page, online, jobs]);
    const markingPlayed = useRef(new Set<string>());
    async function markMusicPlayed(source: string) {
        const job = jobs.find(j => j.service === 'music' && j.result?.files.some(f => f.url === source));
        if (!job) return;
        const index = job.result!.files.findIndex(f => f.url === source);
        if (job.played_indices?.includes(index) || markingPlayed.current.has(source)) return;
        markingPlayed.current.add(source);
        try {
            const result = await api(`/v1/music/jobs/${job.id}/songs/${index}/played`, {method:'POST'});
            setJobs(current => current.map(j => j.id === job.id ? {...j, played_indices: result.played_indices} : j));
        } catch {
            markingPlayed.current.delete(source);
            notify(t('播放状态保存失败，下次播放时重试'));
        }
    }
    useEffect(()=>()=>playbackRequest.current?.abort(),[]);
    useEffect(() => installExclusivePlayback(active => {
        if (active !== audioRef.current) {
            // A newly started preview supersedes a result still waiting for its URL.
            playbackRequest.current?.abort();
            setLoadingAudio(null);
            setPlayingUrl(null);
        }
    }), []);
    async function media(url: string, name: string, download = false, queue?:PlaybackTrack[]) {
        if(!download){
            const contextQueue=page==='library'?sounds.map(sound=>({url:sound.url,name:sound.name})):jobs.filter(job=>page==='jobs'||job.service===page).flatMap(job=>(job.result?.files||[]).map(file=>({url:file.url,name:file.title||file.path.split(/[\\/]/).pop()||name})));
            playbackQueue.current=queue||(contextQueue.some(track=>track.url===url)?contextQueue:[{url,name}]);
            playbackRequest.current?.abort();
            const controller=new AbortController();playbackRequest.current=controller;
            try{
                if(player?.source===url&&audioRef.current&&!audioRef.current.error){
                    setLoadingAudio(null);
                    if(audioRef.current.paused){pauseOtherAudio(audioRef.current);await audioRef.current.play();}else audioRef.current.pause();
                    return;
                }
                pauseOtherAudio(null);setPlayingUrl(null);setLoadingAudio(url);
                const c=connRef.current;if(!c)throw Error(t('API 服务尚未连接'));
                const response=await fetch(c.base+'/v1/playback',{method:'POST',headers:{Authorization:`Bearer ${c.token}`,'Content-Type':'application/json'},body:JSON.stringify({source:url}),signal:controller.signal});
                if(!response.ok)throw Error(t('音频文件获取失败'));
                const link=await response.json();
                if(!controller.signal.aborted)setPlayer({url:c.base+link.url,name,source:url});
            }catch(e){if(!controller.signal.aborted){setLoadingAudio(null);notify(String(e));}}
            return;
        }
        await act('audio', async () => {
            if(!download && player?.source===url && audioRef.current){
                if(audioRef.current.paused){pauseOtherAudio(audioRef.current);await audioRef.current.play();}else audioRef.current.pause();
                return;
            }
            const c = connRef.current;
            if (!c) throw Error(t('API 服务尚未连接'));
            let destination: string | null = null;
            if (download && isTauri()) {
                const extension = name.split('.').pop()?.toLowerCase() || 'wav';
                destination = await save({defaultPath:name, filters:[{name:extension.toUpperCase(),extensions:[extension]}]});
                if (!destination) return;
                notify(t('正在保存文件…'));
            }
            const response = await fetch(c.base + url, {headers:{Authorization:`Bearer ${c.token}`}});
            if (!response.ok) throw Error(t('音频文件获取失败'));
            if (destination) {
                // Raw IPC avoids expanding large audio buffers into JSON number arrays.
                const encodedPath = JSON.stringify(destination).replace(/[^\x20-\x7E]/g, char=>'\\u'+char.charCodeAt(0).toString(16).padStart(4,'0'));
                await invoke('save_download', new Uint8Array(await response.arrayBuffer()), {headers:{'x-save-path':encodedPath}});
                notify(t('已保存到：{0}', destination));
                return;
            }
            const blob = URL.createObjectURL(await response.blob());
            if (download) {
                const a=document.createElement('a');a.href=blob;a.download=name;
                document.body.appendChild(a);a.click();a.remove();
                setTimeout(()=>URL.revokeObjectURL(blob),60000);
            } else {
                setPlayingUrl(null);
                setPlayer(old=>{if(old)URL.revokeObjectURL(old.url);return {url:blob,name,source:url};});
            }
        });
    }
    async function browse(name: ServiceName, key: string, directory: boolean) { if (!isTauri()) {
        notify(t("浏览文件夹需要在桌面应用中使用，也可直接填写路径"));
        return;
    } const p = key === 'database' ? await save({ filters: [{ name: 'SQLite', extensions: ['sqlite3', 'db'] }] }) : await open({ directory, multiple: false }); if (typeof p === 'string')
        change(name, key, p); }
    function change(name: ServiceName, key: string, value: string | number | boolean) { setConfig(c => c ? { ...c, [name]: { ...c[name], [key]: value } } : c); setDirty(true); }
    function badge(s?: ServiceState) { return <span className={`badge ${s?.busy ? 'running' : s?.status || ''}`}><Circle size={7} fill="currentColor"/>{s?.busy ? t("处理中") : statuses[s?.status || ''] || t("连接中")}</span>; }
    function playbackEnded(){
        if(!player)return;
        setPlayingUrl(null);setLoadingAudio(null);
        const next=nextTrack(playbackQueue.current,player.source,playbackMode);
        if(next)void media(next.url,next.name,false,playbackQueue.current);
    }
    const playbackModeLabel=playbackMode==='single'?t('单曲循环'):playbackMode==='list'?t('列表循环'):t('顺序播放（不循环）');
    function serviceActions(name: ServiceName) { return <div className="actions"><button type="button" className={'button light playback-mode '+(playbackMode!=='sequence'?'active':'')} title={playbackModeLabel} aria-label={playbackModeLabel} onClick={()=>setPlaybackMode(mode=>mode==='sequence'?'single':mode==='single'?'list':'sequence')}>{playbackMode==='single'?<Repeat1 size={17}/>:playbackMode==='list'?<Repeat size={17}/>:<ArrowRight size={17}/>}</button><button className="button light" onClick={() => setEditing(name)}><Settings2 size={15}/>{t("配置")}</button><button className="button light" disabled={!!busy || !online} onClick={() => restart(name)}><RefreshCw size={15} className={busy === 'restart-' + name ? 'spin' : ''}/>{t("重启")}</button></div>; }
    function jobRows(limit = 200) { return jobs.slice(0, limit).map(j => <div className="job-row" key={j.id}><div className={`small-icon ${j.service}`}>{React.createElement(icons[j.service], { size: 18 })}</div><div className="job-name"><strong>{j.request.operation==='separate'?t('人声＋伴奏'):j.service==='separation'?t('两位说话人'):names[j.service]}</strong><span className="mono muted">{j.id.slice(0, 12)}</span></div><span className={`badge ${j.status}`}>{statuses[j.status]}</span><time>{new Date(j.created * 1000).toLocaleString(locale(), { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}</time><div className="job-controls">{['queued', 'running'].includes(j.status) && <button title={t("取消任务")} className="icon-button" onClick={() => act('cancel', async () => { await api('/v1/jobs/' + j.id, { method: 'DELETE' }); setJobs(await api('/v1/jobs')); })}><Square size={14}/></button>}{j.error && <button className="icon-button" title={j.error} onClick={() => notify(j.error!)}><AlertCircle size={16}/></button>}</div>{page === 'jobs' && j.error && <pre className="job-error">{j.error}</pre>}{page === 'jobs' && j.result?.files.map((f, i) => <div className="file-result" key={i}><FileAudio size={15}/>{f.tag==='vocals'?t('人声'):f.tag==='instrumental'?t('伴奏'):f.speaker ? t("说话人 {0}", f.speaker) : t("歌曲 / 音频 {0}", i + 1)} · {f.duration?.toFixed(1)} s · {f.sample_rate} Hz <button className="text-button file-play" title={t("播放结果 {0}", i + 1)} onClick={() => media(f.url, f.path.split(/[\\/]/).pop()!)}><PlaybackMark source={f.url} label={t("播放")}/></button><button className="text-button" onClick={() => media(f.url, f.path.split(/[\\/]/).pop()!, true)}><Download size={14}/>{t("下载")}</button><RevealFileButton path={f.path}/></div>)}</div>); }
    const fieldLabels: Record<string, string> = { stems_model_path:t("歌曲人声分离模型文件"), breeze_runtime_dir:t('Breeze 推理代码目录'), breeze_model_dir:t('Breeze 模型目录'), breeze_output_dir:t('Breeze 输出目录'), breeze_cfg_scale:t('Breeze 默认引导系数'), breeze_fast:t('Breeze 加速模式（更多显存）'), qwen_dir: t("Qwen2.5-Omni-3B 模型目录"), cpu_offload: t("CPU 卸载（节省显存）"), python: t("独立 Python 解释器"), lora_dir: t("YuE2 LoRA 目录"), runtime_dir: t("模型运行代码目录"), clone_model_dir: t("参考音色模型目录"), voices_dir: t("预设音色参考目录"), speaker: t("默认预设音色"), language: t("默认语言"), temperature: t("采样温度"), max_new_tokens: t("语音生成 Token 上限"), diffusion_steps: t("转换采样步数"), inference_cfg_rate: t("音色引导系数"), length_adjust: t("时长倍率"), model_path: t("YuE2 模型文件"), encoder_path: t("SheetSage2 文件（音频参考 / Cover 转谱）"), seconds: t("默认生成时长 / 秒"), num_inference_steps: t("采样步数"), cfg_scale: t("提示词引导系数"), sigma_shift: t("采样调度偏移"), model_dir: t("完整模型目录"), output_dir: t("输出目录"), directory: t("音效根目录"), database: t("SQLite 数据库"), ffmpeg: t("FFmpeg 程序"), device: t("计算设备"), default_count: t("默认生成数量"), steps: t("采样步数"), cfg: t("引导系数 CFG"), max_duration: t("最大音频时长 / 秒"), timeout_seconds: t("任务超时 / 秒"), segment_seconds: t("分段处理阈值 / 秒") };
    function configForm(name: ServiceName) { if (!config)
        return null; return <><div className="toggle-row"><div><strong>{t("随程序启动服务")}</strong><p>{t("未配置或检查失败时保留为待配置状态")}</p></div><button role="switch" aria-checked={Boolean(config[name].enabled)} className={`switch ${config[name].enabled ? 'on' : ''}`} onClick={() => change(name, 'enabled', !config[name].enabled)}><span /></button></div><div className="form-grid">{Object.entries(config[name]).filter(([k]) => k !== 'enabled').map(([key, value]) => <label key={key} className={typeof value === 'string' && key !== 'device' ? 'wide' : ''}>{fieldLabels[key] || key}{typeof value === 'boolean' ? <select value={String(value)} onChange={e => change(name, key, e.target.value === 'true')}><option value="true">{t("开启")}</option><option value="false">{t("关闭")}</option></select> : key === 'speaker' ? <select value={String(value)} onChange={e => change(name, key, e.target.value)}>{voices.map(v => <option key={v.id} value={v.id}>{t(v.name)} · {t(v.description)}</option>)}</select> : key === 'language' ? <select value={String(value)} onChange={e => change(name, key, e.target.value)}>{languages.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select> : key === 'device' ? <select value={String(value)} onChange={e => change(name, key, e.target.value)}><option value="cuda">NVIDIA GPU · CUDA</option><option value="cpu">CPU</option></select> : <div className="input-with-button"><input value={String(value)} type={typeof value === 'number' ? 'number' : 'text'} onChange={e => change(name, key, typeof value === 'number' ? Number(e.target.value) : e.target.value)}/>{typeof value === 'string' && <button className="icon-button" title={t("选择路径")} onClick={() => browse(name, key, ['breeze_runtime_dir','breeze_model_dir','breeze_output_dir','qwen_dir', 'runtime_dir', 'lora_dir', 'model_dir', 'clone_model_dir', 'voices_dir', 'output_dir', 'directory'].includes(key))}><FolderOpen size={17}/></button>}</div>}</label>)}</div></>; }
    return <ApiReadyContext.Provider value={online}><PlaybackContext.Provider value={playingUrl}><PlaybackLoadingContext.Provider value={loadingAudio}><div className="app"><aside><div className="brand"><div className="brand-icon"><AudioLines size={23}/></div><div>LOCAL AI<span>{t("本地智能服务中心")}</span></div></div><div className="workspace"><span className="workspace-dot"/>{t("本地工作空间")}<span className="tag">LOCAL</span></div><div className="nav-label">{t("工作台")}</div><nav>{nav.map((n, i) => <React.Fragment key={n.id}>{i === 10 && <div className="nav-label secondary">{t("管理")}</div>}<button className={page === n.id ? 'selected' : ''} onClick={() => setPage(n.id)}><n.icon size={18}/>{n.label}{n.id === 'jobs' && jobs.filter(j => j.status === 'running' || j.status === 'queued').length > 0 && <span className="nav-count">{jobs.filter(j => j.status === 'running' || j.status === 'queued').length}</span>}</button></React.Fragment>)}</nav><div className="sidebar-foot"><div className="local-note"><span className={`dot ${online ? 'green' : ''}`}/>{online ? t("本地 API 已连接") : t("等待 API 连接")}</div><span className="mono">127.0.0.1:{bootstrap.port}</span><div className="version">Local AI Service <span>v0.1.0</span></div></div></aside>
 <div className="main-shell"><header><div className="breadcrumb">{t("工作空间")}<ChevronRight size={14}/><h1>{active.label}</h1></div><div className="header-right">{page === 'overview' ? <button className="button primary" disabled={!!busy || !online} onClick={() => act('all', async () => { for (const name of ['music', 'denoise', 'separation', 'sfx', 'tts', 'vc', 'auk', 'library'] as ServiceName[])
        await api(`/v1/services/${name}/restart`, { method: 'POST' }); setStatus(await api('/v1/status')); notify(t("全部服务已重新检查")); })}><RefreshCw size={16} className={busy === 'all' ? 'spin' : ''}/>{t("重启全部服务")}</button> : ['music', 'denoise', 'separation', 'sfx', 'tts', 'vc', 'auk', 'library'].includes(page) ? serviceActions(page as ServiceName) : null}</div></header><main>
 {!online && <div className="connection-warning"><AlertCircle size={18}/><div><strong>{t("API 服务尚未连接")}</strong><p>{error || t("正在启动，请稍候…")}</p>{!isTauri() && <div className="actions"><input placeholder={t("输入本地 API Key")} type="password" value={browserToken} onChange={e => setBrowserToken(e.target.value)}/><button className="button light" onClick={() => { sessionStorage.setItem('local-ai-token', browserToken); connectService(); }}>{t("连接")}</button></div>}</div><button className="button light" onClick={() => { setPage('settings'); }}>{t("运行环境")}</button></div>}
 {page === 'overview' && <><div className="stats"><div><span><Server size={16}/>{t("就绪服务")}</span><strong>{Object.values(status?.services || {}).filter(s => s.status === 'ready').length}<small> / 8</small></strong><p>{t("独立配置，统一管理")}</p></div><div><span><Cpu size={16}/>{t("模型资源策略")}</span><strong className="word">{t("按需加载")}</strong><p>{t("启动 API 不加载模型")}</p></div><div><span><Clock3 size={16}/>{t("等待中的任务")}</span><strong>{jobs.filter(j => j.status === 'queued').length.toString().padStart(2, '0')}</strong><p>{status?.current_job ? t("1 个任务正在运行") : t("当前没有推理任务")}</p></div><div><span><Check size={16}/>{t("已完成任务")}</span><strong>{jobs.filter(j => j.status === 'succeeded').length.toString().padStart(2, '0')}</strong><p>{t("最近 200 条任务记录")}</p></div></div><div className="section-title"><h2>{t("你的 AI 服务")}<span>8</span></h2><span className="muted"><span className="dot green"/>{t("应用启动时自动检查")}</span></div><div className="service-grid">{(['music', 'denoise', 'separation', 'sfx', 'tts', 'vc', 'auk', 'library'] as ServiceName[]).map(name => <section className="service-card" key={name}><div className="card-top"><div className={`service-icon ${name}`}>{React.createElement(icons[name], { size: 25 })}</div>{badge(status?.services[name])}</div><h3>{names[name]}</h3><span className="model-name">{name === 'auk' ? t("AuK · 语音生成与编辑") : name === 'music' ? 'YuE2 · 3B' : name === 'denoise' ? 'MossFormer2 · SE 48K' : name === 'tts' ? 'Qwen3-TTS / Breeze TTS 2' : name === 'vc' ? 'Seed-VC' : name === 'sfx' ? 'MOSS-SoundEffect · v2.0' : name === 'separation' ? 'MossFormer2 · SS 16K' : t("本地文件 · SQLite")}</span><p className="service-description">{name === 'auk' ? t("用指令编辑语音、清唱歌词、情绪与音色，增强和提取人声。") : name === 'music' ? t("输入歌词与音乐风格，生成带人声的完整歌曲。") : name === 'denoise' ? t("支持音频与视频输入，输出清晰的降噪音频。") : name === 'tts' ? t("选择预设音色或参考声音，让文字自然地说出来。") : name === 'vc' ? t("保留原音频内容，将声音转换为指定音色。") : name === 'sfx' ? t("输入中文或英文描述，生成环境、动作与物体音效。") : name === 'separation' ? t("将两个人混合的语音分开，输出两条独立音轨。") : t("按目录自动分类，让其他应用随时取用音效。")}</p><div className="service-meta"><span>{name === 'library' ? t("存储方式") : t("加载策略")}</span><strong>{name === 'library' ? t("本地索引") : t("任务结束即释放")}</strong></div><div className="service-message" title={serviceMessage(status?.services[name]?.message || '')}>{status?.services[name]?.pending_restart ? t("配置已更改 · 等待手动重启") : serviceMessage(status?.services[name]?.message || '') || t("正在连接服务…")}</div><div className="card-footer"><button className="text-button" onClick={() => setPage(name)}>{t("打开服务")}<ArrowUpRight size={15}/></button><button title={t("服务配置")} className="icon-button" onClick={() => setEditing(name)}><Settings2 size={17}/></button></div></section>)}</div><div className="resource-note"><div className="note-icon"><Cpu size={20}/></div><div><strong>{t("服务常驻，模型按需工作")}</strong><p>{t("所有 AI 服务串行推理，每次任务完成后释放进程和显存。音效库查询无需 GPU。")}</p></div><span className="outline-tag">{t("资源友好")}</span></div><section className="panel recent"><div className="section-title"><h2>{t("最近任务")}</h2><button className="text-button" onClick={() => setPage('jobs')}>{t("查看全部")}<ChevronRight size={15}/></button></div>{jobs.length ? jobRows(4) : <div className="empty"><ListMusic size={28}/><strong>{t("还没有任务")}</strong><p>{t("打开音乐生成或音频降噪，开始你的第一次创作。")}</p></div>}</section></>}
 {page === 'music' && <div className="two-column music-workspace"><section className="panel"><div className="section-title"><h2><Music2 size={18}/>{variation ? t("创作新版本") : t("创作歌曲")}</h2>{badge(status?.services.music)}</div>{variation && <div className="source-song"><span>{t("来源歌曲 ·")}{variation.action === 'cover' ? 'Cover' : variation.action === 'remix' ? 'Remix' : variation.action === 'score' ? t("改曲") : t("改词")}</span><strong>{variation.title}</strong><p>{variation.reference === 'audio' ? t("原音频 → 提取参考曲谱 → 生成新版本") : t("原曲谱 → 编辑旋律 / 和弦 → 生成新版本")}</p><button className="text-button" onClick={() => { setVariation(null); setVariationAbc('');  }}>{t("移除参考，独立创作")}</button></div>}<MusicReference api={api} service="music" file={musicReference} disabled={!!busy} onChange={file=>{setMusicReference(file); if(file){setVariation(null);setVariationAbc('');if(mode==='off')setMode('full');setLora({...lora,planner_lora:null,lora_provider:lora.acoustic_lora?lora.lora_provider:'none'});}}}/><button className="button light full" disabled={!musicReference || !!busy || !online || status?.services.music.status !== 'ready'} onClick={() => act('transcribe', transcribeReference)}>{t('从参考音频生成歌谱')}</button><p className="muted">{t('仅提取参考音频的旋律或旋律与和弦，不生成新歌。使用下方乐谱规划选项，最长 15 分钟。')}</p><label>{t("歌名")}<span className="label-hint">{t("可选")}</span><input value={songTitle} maxLength={120} onChange={e => setSongTitle(e.target.value)} placeholder={t("留空自动命名：yyyyMMdd-hhmmss_n")}/></label><MusicPresets style={style} hasReference={!!musicReference||!!variation} disabled={!!busy} duration={musicMinutes} setDuration={setMusicMinutes} apply={(prompt,instrumental,vocal)=>{setStyle(prompt);if(instrumental){if(lyrics.trim()!=='[Instrumental]')savedVocalLyrics.current=lyrics;setLyrics('[Instrumental]');}else if(vocal&&lyrics.trim()==='[Instrumental]'){setLyrics(savedVocalLyrics.current); }notify(t('预设已填入，可继续修改后生成。'));}}/><label>{t("音乐风格")}<textarea ref={musicStyleRef} placeholder={t('留空不指定曲风，由模型发挥')} rows={3} value={style} onChange={e => setStyle(e.target.value)}/></label><label>{t("歌词")}<span className="label-hint">{t("可使用 [Verse] / [Chorus] 段落标记")}</span><textarea ref={lyricsRef} placeholder={t('留空生成纯音乐，不演唱')} className="lyrics" rows={12} value={lyrics} onChange={e => setLyrics(e.target.value)}/></label><div className="form-grid"><label>{t("生成数量")}<select value={count} onChange={e => setCount(Number(e.target.value))}><option value={1}>{t("1 首")}</option><option value={2}>{t("2 首")}</option></select></label><label>{t("随机种子")}<input type="number" value={seed} onChange={e => setSeed(Number(e.target.value))}/></label><label className="wide">{t("乐谱规划")}<select value={mode} onChange={e => { setMode(e.target.value); if (e.target.value === 'off')
        setGenerateScore(false); }}><option value="full">{t("完整规划 · 旋律与和弦")}</option><option value="melody">{t("仅旋律")}</option><option value="off" disabled={!!variation || !!musicReference}>{t("直接生成")}</option></select></label></div><label className="score-toggle"><input type="checkbox" checked={generateScore} disabled={mode === 'off'} onChange={e => setGenerateScore(e.target.checked)}/>{t("生成曲谱 · 预览与下载 ABC")}</label><p className="muted">{mode === 'off' ? t("直接生成不产生曲谱，请选择旋律或完整规划。") : t("默认关闭；关闭只是不保存曲谱，不改变乐谱规划方式。")}</p>{variation?.reference === 'score' && <label>{t("编辑曲谱 · ABC")}<textarea className="score-editor" rows={10} value={variationAbc} onChange={e => setVariationAbc(e.target.value)}/><span className="label-hint">{t("支持修改音符、节奏、调号和和弦；原曲谱保留。")}</span></label>}<details className="music-advanced"><summary>{t("高级选项 · LoRA")}</summary><MusicLora api={api} value={lora} onChange={setLora} onConfigure={() => setEditing('music')} mode={mode} onDirect={() => { if (variation || musicReference) {
        notify(t("参考歌曲需要旋律或完整规划模式"));
        return;
    } setMode('off'); setGenerateScore(false); }}/></details><button className="button primary full" disabled={!!busy || !online || status?.services.music.status !== 'ready' || (lora.lora_provider !== 'none' && !lora.acoustic_lora && !lora.planner_lora)} onClick={() => act('generate', generateMusic)}>{busy === 'generate' ? <Loader2 className="spin" size={17}/> : <Music2 size={17}/>}{variation ? t("生成新版本") : t("生成歌曲")}</button></section><MusicSongs remove={trashMusicJob} online={online} annotated={(id,index,value)=>setJobs(current=>current.map(j=>j.id===id?{...j,song_annotations:{...j.song_annotations,[String(index)]:value}}:j))} workspace={musicWorkspace} setWorkspace={setMusicWorkspace} api={api} jobs={jobs} media={media} disabled={!!busy || !online} separate={async(job,index)=>{await api('/internal/music/separate',{method:'POST',body:JSON.stringify({job_id:job.id,audio_index:index})});setJobs(await api('/v1/jobs'));notify(t('人声分离已加入队列，完成后人声与伴奏会出现在列表中。'));}} reuse={reuseSong} save={async (id, index, title, group) => { await api(`/v1/music/jobs/${id}/songs/${index}`, { method: 'PUT', body: JSON.stringify({ title, group }) }); setJobs(await api('/v1/jobs')); notify(t("歌名与分组已保存")); }}/></div>}
 {page === 'music' && <MusicScores jobs={jobs} api={api} download={media} busy={!!busy || !online || status?.services.music.status !== 'ready'} regenerate={async (job, score, abc) => { setBusy('rescore'); try {
        if (!isTauri())
            throw new Error(t("改谱功能仅限桌面应用使用"));
        await api('/internal/music/regenerate', { method: 'POST', body: JSON.stringify({ workspace: musicWorkspace || '', job_id: job.id, score_index: Number(score.url.split('/').pop()), abc }) });
        setJobs(await api('/v1/jobs'));
        notify(t("改谱生成任务已提交，完成后请选择新曲谱"));
    }
    finally {
        setBusy('');
    } }}/>}
 {page === 'auk' && <AukEditor api={api} jobs={jobs} ready={online && status?.services.auk?.status === 'ready'} onSubmitted={async () => { setJobs(await api('/v1/jobs')); notify(t("音频编辑任务已提交")); }} media={media}/>}
 {page === 'denoise' && <div className="two-column"><section className="panel"><div className="section-title"><h2>{t("新建降噪任务")}</h2>{badge(status?.services.denoise)}</div><ReferenceMedia file={upload} onChange={setUpload} disabled={!!busy} api={api} service="denoise" label={t("原音频或视频")}/><div className="inline-note">{t("视频将提取第一条音轨进行人声降噪，输出 48 kHz 单声道 WAV。")}</div><button className="button primary full" disabled={!upload || !!busy || status?.services.denoise.status !== 'ready'} onClick={() => act('denoise', async () => { const data = {upload_id:await uploadReference(upload!,api)}; await api('/v1/denoise?wait=false', { method: 'POST', body: JSON.stringify({ upload_id: data.upload_id }) }); setJobs(await api('/v1/jobs')); notify(t("降噪任务已加入队列")); setPage('jobs'); })}><Waves size={17}/>{busy === 'denoise' ? t("正在上传…") : t("开始降噪")}</button></section><section className="panel info-card"><h2>MossFormer2 SE 48K</h2><p>{t("专用于语音增强，适合对白、采访与人声录音。音乐和环境音请先用片段试听处理效果。")}</p><dl><dt>{t("采样率")}</dt><dd>48,000 Hz</dd><dt>{t("处理设备")}</dt><dd>{config?.denoise.device === 'cuda' ? 'NVIDIA GPU' : 'CPU'}</dd><dt>{t("分段长度")}</dt><dd>{config?.denoise.segment_seconds}{t("秒")}</dd></dl><button className="button light full" onClick={() => setEditing('denoise')}>{t("配置模型")}</button></section></div>}
 {page === 'separation' && <div className="two-column"><section className="panel"><div className="section-title"><h2>{t("新建人声分离任务")}</h2>{separationMode==='both'?<span className="muted">{t('两位说话人')} {badge(status?.services.separation)} · {t('人声＋伴奏')} {badge(status?.services.music)}</span>:badge(status?.services[separationMode==='music'?'music':'separation'])}</div><label>{t('分离模式')}<select value={separationMode} onChange={e=>setSeparationMode(e.target.value)}><option value="speakers">{t('两位说话人')}</option><option value="music">{t('人声＋伴奏')}</option><option value="both">{t('同时执行两者')}</option></select></label><ReferenceMedia file={upload} onChange={setUpload} disabled={!!busy} api={api} service={separationMode==='music'?'music':'separation'} label={t("原音频或视频")}/><div className="inline-note">{separationMode==='both'?t('一次提交两种分离，依次生成说话人 1、说话人 2、人声和伴奏，可在任务记录分别试听对比。'):separationMode==='music'?t('分离歌曲人声与伴奏，输出两条 44.1 kHz 立体声 WAV，最长 15 分钟。'):t('分离两位说话人的混合语音，输出两条 16 kHz 单声道 WAV。')}</div><button className="button primary full" disabled={!upload || !!busy || !online || (separationMode!=='music'&&status?.services.separation.status!=='ready') || (separationMode!=='speakers'&&status?.services.music.status!=='ready')} onClick={() => act('separation', async () => { const data = {upload_id:await uploadReference(upload!,api)}; let submitted=0;try{if(separationMode!=='music'){await api('/v1/separate?wait=false',{method:'POST',body:JSON.stringify({upload_id:data.upload_id})});submitted++;}if(separationMode!=='speakers'){await api('/internal/music/separate-upload',{method:'POST',body:JSON.stringify({upload_id:data.upload_id,title:upload!.name.replace(/\.[^.]+$/,'').slice(0,120)})});submitted++;}}catch(e){if(submitted)throw Error(t('已提交 {0} 个任务，其余提交失败：{1}',submitted,String(e)));throw e;} setJobs(await api('/v1/jobs')); notify(separationMode==='both'?t('两种分离任务已加入队列，完成后可试听四条音轨。'):t("人声分离任务已加入队列")); setPage('jobs'); })}><Users size={17}/>{busy === 'separation' ? t("正在上传…") : t("开始分离")}</button></section>{separationMode!=='speakers'?<section className="panel info-card"><h2>{separationMode==='both'?'MossFormer2 SS 16K + HDemucs':'HDemucs'}</h2>{separationMode==='both'&&<><p>{t('分离两位说话人的混合语音，输出两条 16 kHz 单声道 WAV。')}</p><button className="button light full" onClick={()=>setEditing('separation')}>{t('两位说话人')} · {t('配置模型')}</button></>}<p>{t('分离歌曲人声与伴奏，输出两条 44.1 kHz 立体声 WAV，最长 15 分钟。')}</p><p className="muted">{t('使用音乐服务的运行环境、设备与分离模型配置；首次使用可自动下载分离模型。')}</p><button className="button light full" onClick={()=>setEditing('music')}>{t('配置模型')}</button></section>:<section className="panel info-card"><h2>MossFormer2 SS 16K</h2><p>{t("用于两位说话人的混合语音。输出编号仅代表两条音轨，不识别人名，也不保证跨任务编号一致。")}</p><dl><dt>{t("采样率")}</dt><dd>16,000 Hz</dd><dt>{t("处理设备")}</dt><dd>{config?.separation.device === 'cuda' ? 'NVIDIA GPU' : 'CPU'}</dd><dt>{t("输出音轨")}</dt><dd>{t("2 条独立说话人音轨")}</dd><dt>{t("分段阈值")}</dt><dd>{config?.separation.segment_seconds}{t("秒")}</dd></dl><button className="button light full" onClick={() => setEditing('separation')}>{t("配置模型")}</button></section>}</div>}
 {page === 'sfx' && <div className="two-column"><section className="panel"><div className="section-title"><h2><AudioLines size={18}/>{t("生成音效")}</h2>{badge(status?.services.sfx)}</div><label>{t("音效描述")}<textarea rows={7} value={sfxPrompt} onChange={e => setSfxPrompt(e.target.value)} placeholder={t("描述声音的来源、环境、节奏与变化，支持中文或英文")}/></label><div className="form-grid"><label>{t("时长 / 秒")}<input type="number" min={1} max={30} step={0.1} placeholder={t("使用服务默认值")} value={sfxSeconds} onChange={e => setSfxSeconds(e.target.value)}/></label><label>{t("数量")}<input type="number" min={1} max={4} placeholder={t("使用服务默认值")} value={sfxCount} onChange={e => setSfxCount(e.target.value)}/></label><label>{t("随机种子")}<input type="number" min={0} max={4294967292} value={seed} onChange={e => setSeed(Number(e.target.value))}/></label></div><button className="button primary full" disabled={!!busy || !online || status?.services.sfx?.status !== 'ready' || !sfxPrompt.trim()} onClick={() => act('sfx', async () => { await api('/v1/sfx/generate?wait=false', { method: 'POST', body: JSON.stringify({ prompt: sfxPrompt, seed, ...(sfxSeconds ? { seconds: Number(sfxSeconds) } : {}), ...(sfxCount ? { count: Number(sfxCount) } : {}) }) }); setJobs(await api('/v1/jobs')); setPage('jobs'); notify(t("音效生成任务已提交")); })}><Play size={16}/>{t("生成音效")}</button></section><section className="panel"><h2>MOSS-SoundEffect v2.0</h2><p>{t("支持自然环境、动物、机械和人物动作等音效。输出 48 kHz 单声道 WAV，最长 30 秒。")}</p><div className="inline-note">{t("默认 10 秒、1 个音效、100 步、引导系数 4。可在服务配置中修改默认参数。每个结果使用递增种子，完成后可在任务记录中试听或下载。")}</div><p className="muted">{t("模型只在任务执行时加载，结束后释放显存。模型或运行环境缺失时，请完成配置并手动重启此服务。")}</p></section></div>}
 {page === 'tts' && <TtsPanel api={api} media={media} online={online} configure={()=>setEditing('tts')} submitted={()=>{api('/v1/jobs').then(setJobs);setPage('jobs');notify(t('任务已提交'));}}/>}
 {(['vc'] as string[]).includes(page) && <div className="two-column"><section className="panel"><div className="section-title"><h2>{page === 'tts' ? t("让文字说话") : t("转换音色")}</h2>{badge(status?.services[page as ServiceName])}</div>{page === 'tts' ? <><label>{t("要朗读的文字")}<textarea rows={6} maxLength={2000} value={ttsText} onChange={e => setTtsText(e.target.value)}/></label><label>{t("语言")}<select value={ttsLanguage} onChange={e => setTtsLanguage(e.target.value)}>{languages.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label></> : <ReferenceMedia file={voiceSource} onChange={setVoiceSource} disabled={!!busy} api={api} service="vc" label={t("原音频或视频")}/>}<label>{t("目标音色")}<select value={voiceMode} onChange={e => setVoiceMode(e.target.value)}><option value="preset">{t("选择预设音色")}</option><option value="reference">{t("使用参考音频")}</option></select></label>{voiceMode === 'preset' ? <><label>{t("预设音色")}<select value={selectedVoice} onChange={e => setSelectedVoice(e.target.value)}>{voices.map(v => <option key={v.id} value={v.id} disabled={page === 'vc' && !v.vc_available}>{t(v.name)} · {t(v.description)}{page === 'vc' && !v.vc_available ? t("（参考未准备）") : ''}</option>)}</select></label>{voices.find(v => v.id === selectedVoice)?.preview_url && <button className="button light" onClick={() => media(voices.find(v => v.id === selectedVoice)!.preview_url!, selectedVoice + '.wav')}><PlaybackMark source={voices.find(v => v.id === selectedVoice)!.preview_url!} size={15} label={t("试听此音色")}/></button>}{page === 'tts' && <label>{t("表达方式（可选）")}<input placeholder={t("例如：用温柔自然的语气说")} value={ttsInstruct} onChange={e => setTtsInstruct(e.target.value)}/></label>}</> : <><ReferenceMedia file={voiceReference} onChange={setVoiceReference} disabled={!!busy} api={api} service="vc"/><p className="muted">{t("建议使用清晰、单人、无音乐的录音。")}{page === 'tts' ? '3–30' : '3–25'}{t("秒。")}</p>{page === 'tts' && <label>{t("参考音频对应文字（可选）")}<textarea rows={2} value={referenceText} onChange={e => setReferenceText(e.target.value)} placeholder={t("填写准确原文可使用上下文克隆；留空只提取音色")}/></label>}</>}<button className="button primary full" disabled={!!busy || !online || status?.services[page as ServiceName]?.status !== 'ready' || (page === 'tts' ? !ttsText.trim() : !voiceSource) || (voiceMode === 'reference' ? !voiceReference : (page === 'vc' && !voices.find(v => v.id === selectedVoice)?.vc_available))} onClick={submitVoice}><Play size={16}/>{page === 'tts' ? t("生成语音") : t("开始转换")}</button></section><section className="panel"><h2>{page === 'tts' ? t("Qwen3-TTS · 9 个预设音色") : t("Seed-VC · 参考音色转换")}</h2><p>{page === 'tts' ? t("支持中文等 10 种语言。预设涵盖明亮女声、温柔女声、醇厚男声、方言及外语音色，也可上传参考录音克隆音色。") : t("保留原音频中的话语内容，以选择的音色重新输出。预设参考由本 APP 的文字转语音模型生成，也支持你自己的参考录音。")}</p><div className="inline-note">{page === 'tts' ? t("输出 24 kHz 单声道 WAV。长文本建议分段提交，Token 上限可能截断过长语音。") : t("输出 22.05 kHz 单声道 WAV。本版本面向说话声；音乐伴奏建议先移除。时长倍率和引导系数在服务配置中调整。")}</div><p className="muted">{t("任务完成后可在任务记录中试听和下载。模型按需加载，任务结束释放显存。")}</p></section></div>}
 {page === 'library' && <section className="panel"><div className="library-tools"><div className="search"><Search size={17}/><input placeholder={t("搜索音效名称…")} value={q} onChange={e => { setQ(e.target.value); setOffset(0); }}/></div><select value={category} onChange={e => { setCategory(e.target.value); setOffset(0); }}><option value="">{t("全部分类")}</option>{categories.map(c => <option key={c.category}>{c.category}</option>)}</select><button className="button primary" disabled={!!busy || status?.services.library.status !== 'ready'} onClick={() => act('scan', async () => { const r = await api('/v1/sounds/scan', { method: 'POST' }); await loadSounds(); notify(t("已索引 {0} 个音效", r.count)); })}><RefreshCw size={16} className={busy === 'scan' ? 'spin' : ''}/>{busy === 'scan' ? t("正在扫描") : t("扫描目录")}</button></div><div className="library-summary">{t("共")}{total}{t("个音效")}<span>{t("分类来自文件夹结构 · 扫描不会修改原文件")}</span></div>{sounds.length ? <><div className="sound-header"><span>{t("文件名称")}</span><span>{t("分类")}</span><span>{t("大小")}</span><span>{t("操作")}</span></div>{sounds.map(s => <div className="sound-row" key={s.id}><span><FileAudio size={19}/>{s.name}</span><span className="category-pill">{s.category}</span><span>{(s.size / 1024 / 1024).toFixed(2)} MB</span><div className="actions"><button title={t("试听")} className="icon-button" onClick={() => media(s.url, s.name)}><PlaybackMark source={s.url} size={16}/></button><button title={t("下载")} className="icon-button" onClick={() => media(s.url, s.name, true)}><Download size={16}/></button></div></div>)}<div className="pagination"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>{t("上一页")}</button><span>{offset + 1}–{Math.min(offset + 50, total)} / {total}</span><button disabled={offset + 50 >= total} onClick={() => setOffset(offset + 50)}>{t("下一页")}</button></div></> : <div className="empty tall"><LibraryBig size={40}/><strong>{t("建立你的本地音效库")}</strong><p>{t("选择音效目录，重启服务后扫描即可自动分类。")}</p><button className="button light" onClick={() => setEditing('library')}><Plus size={16}/>{t("配置音效目录")}</button></div>}</section>}
 {page === 'jobs' && <section className="panel"><div className="section-title"><h2>{t("全部任务")}</h2><span className="muted">{t("最近 200 条 · 自动刷新")}</span></div>{jobs.length ? jobRows() : <div className="empty tall"><Clock3 size={35}/><strong>{t("暂无任务记录")}</strong><p>{t("生成与降噪任务会显示在这里。")}</p></div>}</section>}
 {page === 'api' && <><div className="api-banner"><div className="service-icon music"><Cable size={27}/></div><div><h2>{t("让你的应用连接本地 AI")}</h2><p>{t("标准 HTTP + JSON · Bearer 认证 · 仅监听本机")}</p></div><span className="badge ready">REST API v1</span></div><section className="panel"><label>{t("服务地址")}<div className="code-line mono">{conn?.base || 'http://127.0.0.1:19876'}</div></label><label>API Key<div className="code-line"><KeyRound size={17}/><code>{tokenVisible ? conn?.token : '••••••••••••••••••••••••••••••••'}</code><button className="text-button" onClick={() => setTokenVisible(!tokenVisible)}>{tokenVisible ? t("隐藏") : t("显示")}</button><button title={t("复制 API Key")} className="icon-button" onClick={() => act('copy', async () => { await navigator.clipboard.writeText(conn?.token || ''); notify(t("API Key 已复制")); })}><Copy size={16}/></button></div></label><div className="endpoint-list">{[['GET', '/v1/tts/models', 'Qwen3-TTS / Breeze TTS 2'], ['GET', '/v1/music/lora-options', t("YuE2 LoRA 方案与可加载文件")], ['GET', '/v1/voices', t("预设音色、特点和试听地址")], ['POST', '/v1/tts/generate', t("文字 + 预设或参考音色 → 语音")], ['POST', '/v1/voice/convert', t("原音频 + 预设或参考音色 → 转换音频")], ['POST', '/v1/sfx/generate', t("中文或英文描述 → 音效列表")], ['POST', '/v1/music/generate', t("歌词与风格 → 歌曲列表")], ['POST', '/v1/uploads', t("上传音频或视频 → upload_id")], ['POST', '/v1/denoise', t("upload_id → 降噪音频列表")], ['POST', '/v1/separate', t("upload_id → 两条说话人音轨")], ['POST', '/v1/separate/file', t("直接上传音频或视频 → 两条音轨")], ['GET', '/v1/jobs/{id}', t("查询异步任务及结果下载地址")], ['GET', '/v1/sounds?category=…&q=…', t("分页与分类搜索音效")], ['GET', '/v1/categories', t("获取分类和文件数量")], ['GET', '/v1/sounds/{id}/audio', t("获取音频文件（支持 Range）")]].map(([method, path, desc]) => <div className="endpoint" key={path}><span className={method.toLowerCase()}>{method}</span><code>{path}</code><p>{desc}</p></div>)}</div><h3>{t("异步调用示例")}</h3><pre className="code-block">{`POST /v1/music/generate?wait=false\nAuthorization: Bearer <API_KEY>\nContent-Type: application/json\n\n{\n  "lyrics": "[Verse]\\n晚风轻轻经过窗台",\n  "style": "Mandarin, indie pop, warm vocals",\n  "count": 2,\n  "seed": 42\n}\n\n// 202 → 轮询 GET /v1/jobs/{id}\n// 成功后使用 result.files[].url 下载音频`}</pre><p className="muted">{t("不传 wait=false 时等待完成，直接返回 files 列表。完整 OpenAPI：")}{conn?.base}{t("/openapi.json；交互文档：/docs。")}</p></section></>}
 {page === 'logs' && <section className="panel"><div className="section-title"><h2>{t("服务日志")}</h2><button className="text-button" onClick={() => act('logs', async () => setLogs(await api('/v1/logs')))}><RefreshCw size={15}/>{t("刷新")}</button></div><pre className="logs">{logs.join('\n') || t("暂无日志")}</pre></section>}
 {page === 'settings' && <><AppearanceSettings translate={t}/><LanguageSettings /><section className="panel settings-panel"><h2>{t("独立运行环境")}</h2><p className="muted">{t("API、音乐、音效与语音处理使用本 APP 内的隔离环境，安装依赖不会修改其他应用。")}</p><label>{t("API Python 解释器")}<div className="input-with-button"><input value={bootstrap.python} onChange={e => setBootstrap({ ...bootstrap, python: e.target.value })}/><button className="icon-button" onClick={() => act('pick', async () => { if (!isTauri())
        return; const p = await open({ multiple: false }); if (typeof p === 'string')
        setBootstrap({ ...bootstrap, python: p }); })}><FolderOpen size={17}/></button></div></label><label>{t("本地 API 端口")}<input type="number" min={1024} max={65535} value={bootstrap.port} onChange={e => setBootstrap({ ...bootstrap, port: Number(e.target.value) })}/></label><div className="inline-note">{t("重启整个 API 会中断当前推理任务。修改模型配置请使用各服务的独立重启。")}</div><button className="button primary" disabled={!!busy || !isTauri()} onClick={() => act('api-restart', async () => { await invoke('restart_api', { config: bootstrap }); connRef.current = null; setConn(null); setOnline(false); notify(t("API 服务正在重新启动")); setTimeout(connectService, 2000); })}><RefreshCw size={16}/>{t("保存并重启 API")}</button><label className="data-dir">{t("配置与日志目录")}<div className="code-line mono">{conn?.data_dir || t("本项目 data/ 或系统应用数据目录")}</div></label></section><div className="resource-note"><Cpu size={22}/><div><strong>{t("GPU 与内存策略")}</strong><p>{t("API 和资源索引始终常驻。只有处理任务时加载模型；同时最多执行一个 AI 任务，退出应用会清理所有子进程。")}</p></div></div></>}
 </main><footer>LOCAL AI SERVICE <span>{t("你的模型，你的数据，你的设备。")}</span></footer></div>
 {editing && <div className="modal-backdrop"><div className="modal"><div className="modal-heading"><div><span className="eyebrow">SERVICE CONFIGURATION</span><h2>{names[editing]}{t("配置")}</h2></div><button title={t("关闭")} className="icon-button" onClick={() => setEditing(null)}><X size={21}/></button></div><div className="modal-body">{status?.services[editing]?.status === 'needs_config' && <div className="inline-warning">{status.services[editing].message}</div>}{configForm(editing)}</div><div className="modal-footer"><span className="muted">{dirty ? t("有未保存的修改") : t("保存后需手动重启此服务")}</span><button className="button light" disabled={!!busy || dirty} onClick={() => restart(editing)}><RefreshCw size={15}/>{t("重启服务")}</button><button className="button primary" disabled={!!busy || !online} onClick={saveConfig}><Save size={15}/>{t("保存配置")}</button></div></div></div>}
 {player && <div className="audio-player"><div className="small-icon music"><AudioLines size={20}/></div><strong>{player.name}</strong><audio ref={audioRef} key={player.url} controls autoPlay loop={playbackMode==='single'} src={player.url} onPlaying={()=>{setLoadingAudio(null);setPlayingUrl(player.source);void markMusicPlayed(player.source);}} onPause={()=>setPlayingUrl(old=>old===player.source?null:old)} onEnded={playbackEnded} onWaiting={()=>{setLoadingAudio(player.source);setPlayingUrl(old=>old===player.source?null:old);}} onError={()=>{setLoadingAudio(null);setPlayingUrl(old=>old===player.source?null:old);notify(t('音频文件获取失败'));}}/><button title={t("关闭播放器")} className="icon-button" onClick={() => { playbackRequest.current?.abort();playbackQueue.current=[];setLoadingAudio(null);URL.revokeObjectURL(player.url); setPlayingUrl(null); setPlayer(null); }}><X size={19}/></button></div>}
 {toast && <div role="status" aria-live="polite" aria-atomic="true" className="toast"><AlertCircle size={17}/><span>{serviceMessage(toast)}</span><button title={t("关闭提示")} aria-label={t("关闭提示")} onClick={dismissToast}><X size={15}/></button></div>}
 </div></PlaybackLoadingContext.Provider></PlaybackContext.Provider></ApiReadyContext.Provider>;
}
initializeTheme('audio');
createRoot(document.getElementById('root')!).render(<App />);

import {RevealFileButton} from './RevealFileButton';
import {t, locale, useLanguage, LanguageSettings, serviceMessage} from './i18n';
import { useEffect, useRef, useState } from 'react';
import { renderAbc } from 'abcjs';
import { Download, ListMusic } from 'lucide-react';
export type Score = {
    path?: string;
    title?: string;
    url: string;
    audio_index: number;
    mode: string;
};
type ScoreJob = {
    id: string;
    service: string;
    status: string;
    created: number;
    error: string | null;
    request: Record<string, unknown>;
    result: {
        scores?: Score[];
    } | null;
};
export function MusicScores({ jobs, api, download, regenerate, busy }: {
    jobs: ScoreJob[];
    api: (path: string) => Promise<any>;
    download: (url: string, name: string, download: boolean) => Promise<void>;
    regenerate: (job: ScoreJob, score: Score, abc: string) => Promise<void>;
    busy: boolean;
}) {
    const [selected, setSelected] = useState('');
    const [abc, setAbc] = useState('');
    const [draft, setDraft] = useState('');
    const [error, setError] = useState('');
    const [warning, setWarning] = useState('');
    const [loading, setLoading] = useState(false);
    const paper = useRef<HTMLDivElement>(null);
    const entries = jobs.filter(j => j.service === 'music').flatMap(j => (j.result?.scores || []).map(s => ({ ...s, job: j })));
    const current = entries.find(s => s.url === selected) || entries[0];
    const url = current?.url;
    const pending = jobs.filter(j => j.service === 'music' && j.request.generate_score && ['queued', 'running'].includes(j.status));
    useEffect(() => {
        let cancelled = false;
        setAbc('');
        setDraft('');
        setError('');
        setLoading(!!url);
        if (url)
            api(url).then(data => { if (!cancelled) {
                setAbc(data.abc);
                setDraft(data.abc);
            } }).catch(e => { if (!cancelled)
                setError(String(e)); }).finally(() => { if (!cancelled)
                setLoading(false); });
        return () => { cancelled = true; };
    }, [url]);
    useEffect(() => {
        if (!paper.current)
            return;
        paper.current.replaceChildren();
        setWarning('');
        if (!abc)
            return;
        try {
            const tunes = renderAbc(paper.current, abc, { responsive: 'resize', staffwidth: 900 });
            if (!tunes.length || !paper.current.querySelector('svg'))
                setWarning(t("无法绘制此曲谱，可查看或下载 ABC 原文。"));
            else if (tunes.some(t => t.warnings?.length))
                setWarning(t("模型曲谱存在不规范记号，部分内容可能无法准确显示。可查看 ABC 原文。"));
        }
        catch {
            setWarning(t("曲谱格式无法完整解析，可查看或下载 ABC 原文。"));
        }
    }, [abc]);
    return <section className="panel score-panel"><div className="section-title"><h2><ListMusic size={18}/>{t("生成的曲谱")}</h2>{current && <div className="actions"><button className="button light" onClick={() => download(current.url + '?download=true', `${(current.title || `song-${current.audio_index + 1}`).replace(/[<>:"/\\|?*]/g, '_')}.abc`, true).catch(e => setError(String(e)))}><Download size={15}/>{t("下载 ABC")}</button><RevealFileButton path={current.path}/></div>}</div>
 <p className="muted">{current?.job.request.operation === 'transcribe' ? t("从参考音频自动识别的旋律 / 和弦谱，可能存在误差，可编辑校正；不是完整乐队总谱。") : t("旋律 / 和弦规划谱，可能与最终演唱、伴奏或截断后的音频不同，不是完整乐队总谱。")}</p>
 {pending.length > 0 && <p role="status">{pending.length}{t("个带曲谱的任务等待完成。完成后可在此查看。")}</p>}
 {entries.length > 0 ? <label>{t("选择歌曲曲谱")}<select value={url} onChange={e => setSelected(e.target.value)}>{entries.map(s => <option key={s.url} value={s.url}>{new Date(s.job.created * 1000).toLocaleString(locale())} · {s.job.id.slice(0, 8)} · {s.title || t("第 {0} 首", s.audio_index + 1)} · {s.mode === 'full' ? t("旋律与和弦") : t("旋律")}</option>)}</select></label> : <p>{t("上传参考音频并点击“从参考音频生成歌谱”，或勾选“生成曲谱”后生成歌曲，完成的曲谱会显示在这里。")}</p>}
 {jobs.filter(j => j.service === 'music' && j.request.operation === 'transcribe' && j.status === 'failed').map(j => <p role="alert" key={j.id}>{String(j.request.title || j.id.slice(0, 8))}: {j.error}</p>)}
 {loading && <p role="status">{t("正在读取曲谱…")}</p>}{error && <p role="alert">{error}</p>}{warning && <p role="status">{warning}</p>}
 <div className="score-paper" ref={paper}/>
 {abc && <><label>{t("编辑 ABC 曲谱")}<textarea className="score-editor" rows={12} value={draft} onChange={e => setDraft(e.target.value)}/></label><div className="actions"><button className="button light" disabled={!draft.trim()} onClick={() => setAbc(draft)}>{t("预览修改")}</button><button className="button primary" disabled={busy || !draft.trim()} onClick={() => current && regenerate(current.job, current, draft).catch(e => setError(String(e)))}>{t("按此曲谱重新生成")}</button></div><p className="muted">{t("沿用原任务歌词、风格、声学 LoRA 和参数，生成 1 首新歌；跳过规划 LoRA。原文件保留，下载 ABC 对应已保存的版本。重新生成可能改变歌声与伴奏。")}</p></>}
 </section>;
}

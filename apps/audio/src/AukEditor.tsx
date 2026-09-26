import {AutocompleteSelect} from '@local-ai/ui';
import {useDraft, useDraftFile} from './useDraft';
import {ReferenceMedia, uploadReference} from './ReferenceMedia';
import {RevealFileButton} from './RevealFileButton';
import {PlaybackMark} from './PlaybackMark';
import {t, locale, useLanguage, LanguageSettings, serviceMessage} from './i18n';
import { useState } from 'react';
import { AudioLines, Play, Download } from 'lucide-react';
type Job = {
    id: string;
    service: string;
    status: string;
    error: string | null;
    result: {
        files: {
            url: string;
            path?: string;
            duration: number;
        }[];
    } | null;
};
export function AukEditor({ api, jobs, ready, onSubmitted, media }: {
    api: (path: string, options?: RequestInit) => Promise<any>;
    jobs: Job[];
    ready: boolean;
    onSubmitted: () => Promise<void>;
    media: (url: string, name: string, download?: boolean) => Promise<void>;
}) {
    const tasks = [
        ['content', t("修改说话内容"), t("把“原文”改成“新内容”。")],
        ['lyrics', t("修改歌词（清唱）"), t("把这段歌词中的“原歌词”改成“新歌词”。")],
        ['pitch', t("调整音高"), t("将音调升高2个半音。")],
        ['speed', t("调整语速"), t("将语速调整为1.25倍。")],
        ['volume', t("调整音量"), t("将音量降低5分贝。")],
        ['emotion', t("改变情绪"), t("将情感转变为开心。")],
        ['timbre', t("描述目标音色"), t("请将这段音频的音色修改为低沉、温暖、自然的成年男声。")],
        ['accent', t("弱化口音"), t("去除地方口音，保留说话人的声音和说话内容。")],
        ['nonverbal', t("呼吸 / 笑声等"), t("去除这段录音中的呼吸声，保留说话内容。")],
        ['whisper', t("耳语转换"), t("将这段正常说话的语音转换为耳语，保留说话人和内容。")],
        ['enhance', t("降噪 / 去混响"), t("去除这段音频中的噪声和混响，保留全部说话人，输出等长的清晰语音。")],
        ['separate', t("按顺序分离说话人"), t("只保留第一个说话人的声音，去掉其他说话人。")],
        ['vocals', t("提取歌曲人声"), t("提取歌曲中的演唱人声，去除伴奏。")],
        ['speaker', t("指定说话人提取"), t("只保留说“目标句子”的说话人的声音。")],
        ['tts', t("描述音色生成语音"), t("请基于下面的描述：“温暖自然的年轻女声”，生成语音内容“你好，欢迎使用本地音频工作室”。")],
        ['clone', t("参考声音生成语音"), t("请用参考音频中相同的声音说：“你好，欢迎使用本地音频工作室”。")],
        ['custom', t("自定义操作"), t("保留说话内容和音色，令语气更加平静自然。")],
    ];
    const [task, setTask] = useDraft('AukEditor.tsx:task', 'content');
    const [instruction, setInstruction] = useDraft('AukEditor.tsx:instruction', tasks[0][2]);
    const [file, setFile] = useDraftFile('AukEditor.tsx:file');
    const [start, setStart] = useDraft('AukEditor.tsx:start', 0);
    const [seconds, setSeconds] = useDraft('AukEditor.tsx:seconds', 10);
    const [target, setTarget] = useDraft('AukEditor.tsx:target', 10);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    async function submit() {
        setBusy(true);
        setError('');
        try {
            let upload_id;
            if (file && task !== 'tts') {
                upload_id = await uploadReference(file, api);
            }
            await api('/v1/audio/edit?wait=false', { method: 'POST', body: JSON.stringify({ task, instruction, upload_id, clip_start: start, clip_seconds: seconds, gen_seconds: target }) });
            await onSubmitted();
        }
        catch (e) {
            setError(String(e));
        }
        finally {
            setBusy(false);
        }
    }
    const useAudio = !!file && task !== 'tts';
    return <div className="two-column"><section className="panel"><h2><AudioLines size={18}/>{t("音频编辑 · AuK")}</h2><p className="muted">{t("用文字描述要修改的内容，处理音频片段。")}</p><label>{t("操作")}<AutocompleteSelect value={task} onChange={e => { setTask(e.target.value); setInstruction(tasks.find(t => t[0] === e.target.value)![2]); }}>{tasks.map(t => <option key={t[0]} value={t[0]}>{t[1]}</option>)}</AutocompleteSelect></label>{task !== 'tts' && <ReferenceMedia file={file} onChange={setFile} disabled={busy} api={api} service="auk"/>}<label>{t("操作指令")}<textarea rows={5} maxLength={4000} value={instruction} onChange={e => setInstruction(e.target.value)}/></label>{task === 'lyrics' && <div className="inline-note">{t("输入必须是无伴奏清唱。混合歌曲请先使用“提取歌曲人声”，下载结果后再编辑歌词。")}</div>}<div className="form-grid">{task !== 'tts' && <><label>{t("片段起点 / 秒")}<input type="number" min={0} max={7200} step={.1} value={start} onChange={e => setStart(Number(e.target.value))}/></label><label>{t("输入片段长度 / 秒")}<input type="number" min={.1} max={29} step={.1} value={seconds} onChange={e => setSeconds(Number(e.target.value))}/></label></>}<label>{t("输出长度 / 秒")}<input type="number" min={.1} max={30} step={.1} value={target} onChange={e => setTarget(Number(e.target.value))}/></label></div><p className="inline-note">{t("输入片段 + 输出合计最多 30 秒。只输出处理后的片段，不自动拼回原文件。调语速时请同时调整输出长度。")}</p>{!ready && <p className="inline-note">{t("服务未就绪，请在配置中设置 AuK 和 Qwen2.5-Omni-3B 路径及独立 Python 环境，再重启此服务。")}</p>}{error && <p role="alert">{error}</p>}<button className="button primary full" disabled={busy || !ready || !instruction.trim() || (!['tts', 'custom'].includes(task) && !file) || (useAudio && seconds + target > 30) || seconds <= 0 || target <= 0 || target > 30 || start < 0} onClick={submit}>{busy ? t("正在提交…") : t("开始处理")}</button></section><section className="panel"><h2>{t("处理结果")}</h2><p className="muted">{t("生成模型可能改变细节，请对比试听。")}</p>{jobs.filter(j => j.service === 'auk').map(j => <article className="music-song" key={j.id}><strong>{j.id.slice(0, 8)}</strong><span className="muted"> · {{ queued: t("排队中"), running: t("处理中"), succeeded: t("已完成"), failed: t("失败"), cancelled: t("已取消") }[j.status] || j.status}</span>{j.error && <p className="song-error">{j.error}</p>}{j.result?.files.map(f => <div className="actions" key={f.url}><span>{f.duration.toFixed(1)}{t("秒")}</span><button className="button light" onClick={() => media(f.url, t("AuK 处理结果"))}><PlaybackMark source={f.url} label={t("试听")}/></button><button className="button light" onClick={() => media(f.url, 'auk-edited.wav', true)}><Download size={14}/>{t("下载")}</button><RevealFileButton path={f.path}/></div>)}</article>)}</section></div>;
}

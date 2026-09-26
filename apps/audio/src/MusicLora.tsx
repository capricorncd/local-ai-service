import {t, locale, useLanguage, LanguageSettings, serviceMessage} from './i18n';
import { useEffect, useState } from 'react';
import { RefreshCw, Settings2 } from 'lucide-react';
export type LoraSelection = {
    lora_provider: string;
    acoustic_lora: string | null;
    planner_lora: string | null;
    acoustic_strength: number;
    planner_strength: number;
};
export const noLora: LoraSelection = { lora_provider: 'none', acoustic_lora: null, planner_lora: null, acoustic_strength: 1, planner_strength: 1 };
type Catalog = {
    directory: string;
    directory_exists: boolean;
    files: {
        id: string;
        name: string;
        targets: string[];
        error: string | null;
    }[];
};
export function MusicLora({ api, value, onChange, onConfigure, mode, onDirect }: {
    api: (path: string) => Promise<Catalog>;
    value: LoraSelection;
    onChange: (value: LoraSelection) => void;
    onConfigure: () => void;
    mode: string;
    onDirect: () => void;
}) {
    const [data, setData] = useState<Catalog | null>(null);
    const [error, setError] = useState('');
    async function refresh() { try {
        setData(await api('/v1/music/lora-options'));
        setError('');
    }
    catch (e) {
        setError(String(e));
    } }
    useEffect(() => { refresh(); }, []);
    function provider(id: string) { onChange({ ...noLora, lora_provider: id }); }
    return <div className="lora-options"><div className="section-title"><h2>{t("可选 LoRA")}</h2><div className="actions"><button className="text-button" onClick={refresh}><RefreshCw size={14}/>{t("刷新文件")}</button><button className="text-button" onClick={onConfigure}><Settings2 size={14}/>{t("目录")}</button></div></div><label>{t("LoRA 方案")}<select value={value.lora_provider} onChange={e => provider(e.target.value)}><option value="none">{t("不使用 LoRA · 基础模型")}</option><option value="speedyrulz">{t("speedyrulz · 声学 / 规划 LoRA")}</option><option value="starnodes2024">{t("Starnodes2024 · 声学 LoRA")}</option></select></label>{value.lora_provider !== 'none' && <><p className="muted">{t("选择已训练的 .safetensors 文件。声学影响音色和制作质感，规划影响旋律与结构。触发词请填写在音乐风格中。")}</p>{value.lora_provider === 'starnodes2024' && mode !== 'off' && <div className="inline-note">{t("此方案建议关闭乐谱规划，以匹配训练方式。")}<button className="text-button" onClick={onDirect}>{t("改为直接生成")}</button></div>}{(!data?.directory_exists || !data.files.length) && <div className="inline-note">{t("还没有 LoRA 文件。请将训练结果放入配置目录，然后刷新。")}<div className="mono">{data?.directory || t("请先配置 LoRA 目录")}</div></div>}{(['acoustic', ...(value.lora_provider === 'speedyrulz' ? ['planner'] : [])] as const).map(target => { const fileKey = (target + '_lora') as 'acoustic_lora' | 'planner_lora'; const strengthKey = (target + '_strength') as 'acoustic_strength' | 'planner_strength'; return <div className="form-grid" key={target}><label>{target === 'acoustic' ? t("声学 LoRA") : t("规划 LoRA")}<select value={value[fileKey] || ''} onChange={e => onChange({ ...value, [fileKey]: e.target.value || null })}><option value="">{t("不加载")}</option>{data?.files.filter(f => !f.error && f.targets.includes(target)).map(f => <option key={f.id} value={f.id}>{f.id}</option>)}</select></label><label>{t("权重（0–3）")}<input type="number" min={0} max={3} step={.1} value={value[strengthKey]} onChange={e => onChange({ ...value, [strengthKey]: Number(e.target.value) })}/></label></div>; })}{data?.files.filter(f => f.error).map(f => <p key={f.id} className="muted">{f.id}：{f.error}</p>)}<p className="muted">{t("同一个合并文件可分别选入声学和规划栏。权重 0 表示不应用对应部分。")}</p></>}{error && <p className="inline-warning">{error}</p>}</div>;
}

import {useDraft} from './useDraft';
import {Sparkles} from 'lucide-react';
import {t} from './i18n';

import styleData from '../server/music_styles.json';
export const musicStyles = styleData;

export function MusicPresets({style, hasReference, disabled, apply, duration, setDuration}: {
  style:string; hasReference:boolean; disabled:boolean;
  apply:(style:string, instrumental:boolean, vocal:boolean)=>void;
  duration:string; setDuration:(value:string)=>void;
}) {
  const [goal,setGoal]=useDraft('MusicPresets.tsx:goal', 'new');
  const [genre,setGenre]=useDraft('MusicPresets.tsx:genre', '');
  const [bpm,setBpm]=useDraft('MusicPresets.tsx:bpm', '');
  const [voice,setVoice]=useDraft('MusicPresets.tsx:voice', 'keep');
  const referenceRequired=['arrange','tempo','expand','similar','male','female'].includes(goal);
  const invalidBpm=!!bpm && (!Number.isFinite(Number(bpm)) || Number(bpm)<30 || Number(bpm)>300);
  function fill() {
    const instrumental=['arrange','tempo','bgm'].includes(goal) || (voice==='instrumental' && !['male','female'].includes(goal));
    const vocal=!instrumental && (['male','female'].includes(goal)||['male','female'].includes(voice));
    let base=musicStyles.find(([name])=>name===genre)?.[1] || style;
    if(instrumental || vocal) base=base.split(/[,，;；\n]+/).filter(tag=>!/(vocal|singing|singer|instrumental|humming|choir|男声|女声|人声|演唱|纯音乐)/i.test(tag)).join(', ');
    const parts=[base];
    if(goal==='arrange')parts.push('Refined instrumental arrangement, balanced instrumentation, clear melodic lead, controlled low end, smooth transitions, detailed dynamics');
    if(goal==='tempo')parts.push('Steady rhythmic pulse, consistent tempo throughout, instrumental arrangement');
    if(goal==='expand')parts.push('Develop the musical theme into a complete piece, intro, contrasting sections, variation, bridge, reprise, resolved outro');
    if(goal==='similar')parts.push('Cohesive instrumentation and mood, fresh arrangement of the reference melody');
    if(bpm)parts.push(`${Number(bpm)} BPM, steady tempo`);
    if(duration)parts.push(`Target duration ${Number(duration)} minutes, complete musical structure, natural ending`);
    if(instrumental)parts.push('Instrumental only, no vocals, no singing, no spoken words, no humming, no choir');
    else if(goal==='male'||(goal!=='female'&&voice==='male'))parts.push('Male lead vocal, warm baritone, clear diction');
    else if(goal==='female'||voice==='female')parts.push('Female lead vocal, clear expressive tone, natural phrasing');
    apply(parts.filter(Boolean).join(', '),instrumental,vocal);
  }
  return <details className="music-presets"><summary><Sparkles size={15}/>{t('创作预设与风格')}</summary>
    <div className="preset-body"><div className="form-grid">
      <label>{t('创作目标')}<select value={goal} disabled={disabled} onChange={e=>{setGoal(e.target.value);if(e.target.value==='expand'&&!duration)setDuration('3');}}>
        <option value="new">{t('全新歌曲')}</option><option value="bgm">{t('纯音乐 BGM')}</option>
        <option value="arrange">{t('优化伴奏（重新编曲）')}</option><option value="tempo">{t('同 BPM 伴奏（填写原 BPM）')}</option>
        <option value="expand">{t('扩展构思为完整歌曲')}</option><option value="similar">{t('参考曲风重新生成')}</option>
        <option value="male">{t('男声版本')}</option><option value="female">{t('女声版本')}</option>
      </select></label>
      <label>{t('人声偏好')}<select value={voice} disabled={disabled||['arrange','tempo','bgm','male','female'].includes(goal)} onChange={e=>setVoice(e.target.value)}><option value="keep">{t('不指定')}</option><option value="instrumental">{t('纯音乐 BGM')}</option><option value="male">{t('男声版本')}</option><option value="female">{t('女声版本')}</option></select></label>
      <label>{t('目标 BPM（可选）')}<input type="number" min={30} max={300} step={1} value={bpm} disabled={disabled} onChange={e=>setBpm(e.target.value)}/></label>
      <label>{t('目标时长 / 分钟')}<input type="number" min={.1} max={15} step={.1} value={duration} disabled={disabled} placeholder={t('使用服务默认值')} onChange={e=>setDuration(e.target.value)}/></label>
    </div><div className="preset-styles">{musicStyles.map(([name,prompt])=><button type="button" disabled={disabled} className={`button light ${genre===name?'active':''}`} key={name} onClick={()=>{setGenre(name);apply(prompt,false,false);}}>{t(name)}</button>)}</div>
    <p className="muted">{t('风格按钮替换风格输入；应用预设会组合目标、风格和参数。纯音乐预设将歌词替换为 [Instrumental]。')}</p>
    {referenceRequired&&!hasReference&&<p className="muted">{t('此预设需要先添加参考音频、视频或选择来源歌曲。')}</p>}
    <button type="button" className="button light" disabled={disabled||(referenceRequired&&!hasReference)||invalidBpm||(goal==='tempo'&&!bpm)||(!!duration&&(!Number.isFinite(Number(duration))||Number(duration)<.1||Number(duration)>15))} onClick={fill}>{t('应用创作预设')}</button>
    <p className="muted">{t('BPM、声线和纯音乐由提示词引导，不保证精确匹配。时长是生成上限；扩展会重生成整曲，不续接原文件。参考输入提取旋律与和弦，不自动识别曲风，请选择或填写风格。')}</p>
    </div></details>;
}

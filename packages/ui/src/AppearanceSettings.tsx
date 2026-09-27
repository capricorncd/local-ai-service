import {LayoutSettings} from './LayoutSettings';
import {DialogActions,InfoTip} from './Dialog';
import {useEffect,useState,useSyncExternalStore} from 'react';
import {getAppearance,subscribeAppearance,setAppearance,resetAppearance,themePresets,validColor,type ThemeMode} from './theme';
import './theme.css';

export function AppearanceSettings({translate=(text:string)=>text,dialogActions=false}:{translate?:(text:string)=>string;dialogActions?:boolean}){
  const value=useSyncExternalStore(subscribeAppearance,getAppearance);
  const [draft,setDraft]=useState(value.accent);
  useEffect(()=>setDraft(value.accent),[value.accent]);
  const t=translate;
  return <><section className="ui-appearance" aria-label={t('外观设置')}>
    <div className="ui-appearance-heading"><h2>{t('外观设置')}</h2><InfoTip text={t('立即生效并自动保存到本机。')} label={t('说明')}/>{dialogActions?<DialogActions><button type="button" onClick={resetAppearance}>{t('恢复默认')}</button></DialogActions>:<button type="button" onClick={resetAppearance}>{t('恢复默认')}</button>}</div>
    <fieldset><legend>{t('显示模式')}</legend><div className="ui-appearance-modes">{([['system','跟随系统'],['light','明亮'],['dark','暗黑']] as const).map(([mode,label])=><label key={mode}><input type="radio" name="appearance-mode" value={mode} checked={value.mode===mode} onChange={()=>setAppearance({...value,mode:mode as ThemeMode})}/>{t(label)}</label>)}</div></fieldset>
    <fieldset><legend>{t('主题色')}</legend><div className="ui-appearance-swatches">{themePresets.map(([name,color])=><button type="button" key={color} aria-label={t(name)} title={t(name)} aria-pressed={value.accent.toLowerCase()===color} onClick={()=>setAppearance({...value,accent:color})}><span style={{background:color}}/>{t(name)}</button>)}</div></fieldset>
    <div className="ui-appearance-custom"><label>{t('自定义颜色')}<input type="color" value={value.accent} onChange={e=>setAppearance({...value,accent:e.target.value})}/></label><label>{t('颜色值')}<input type="text" spellCheck={false} value={draft} maxLength={7} aria-invalid={!validColor(draft)} placeholder="#16847d" onChange={e=>{const color=e.target.value;setDraft(color);if(validColor(color))setAppearance({...value,accent:color});}} onBlur={()=>{if(!validColor(draft))setDraft(value.accent);}}/></label></div>

  </section><LayoutSettings/></>;
}

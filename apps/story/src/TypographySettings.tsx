import {useEffect,useState,useSyncExternalStore} from 'react';
import {api} from './api';
import {defaultTypography,getTypography,setTypography,subscribeTypography,Typography} from './typography';

export function TypographySettings(){
 const value=useSyncExternalStore(subscribeTypography,getTypography);
 const [fonts,setFonts]=useState<string[]>([]),[query,setQuery]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(true);
 async function refresh(){setLoading(true);setError('');try{const r=await api<{fonts:string[];available:boolean}>('/v1/system/fonts');setFonts(r.fonts);if(!r.available)setError('当前系统不支持字体枚举，可继续使用系统默认字体。');}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setLoading(false);}}
 useEffect(()=>{void refresh();},[]);
 function update(next:Typography){try{setTypography(next);setError('');}catch{setError('无法保存字体设置，请检查本机存储是否可用。');}}
 const options=fonts.filter(f=>f.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
 if(value.fontFamily&&!options.includes(value.fontFamily))options.unshift(value.fontFamily);
 return <section className="settings-card typography-settings" aria-label="字体与字号"><div className="typography-heading"><h2>字体与字号</h2><button type="button" onClick={()=>{update(defaultTypography);setQuery('');}}>恢复默认字体</button></div>
  <label>基础字号<div className="font-size-controls"><input aria-label="基础字号" type="range" min={12} max={24} step={1} value={value.fontSize} onChange={e=>update({...value,fontSize:+e.target.value})}/><output>{value.fontSize} px</output><select aria-label="字号数值" value={value.fontSize} onChange={e=>update({...value,fontSize:+e.target.value})}>{Array.from({length:13},(_,i)=>i+12).map(n=><option key={n} value={n}>{n} px{n===16?'（默认）':''}</option>)}</select></div></label>
  <div className="fields"><label>搜索系统字体<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="输入字体名称，如 微软雅黑、Arial"/></label><label>界面字体<select aria-label="界面字体" value={value.fontFamily} onChange={e=>update({...value,fontFamily:e.target.value})}><option value="">系统默认字体</option>{options.map(f=><option value={f} key={f}>{f}</option>)}</select></label></div>
  <div className="font-preview"><b>剧本与分镜 · Storyboard</b><p>雨水顺着发梢滴落。镜头缓缓推进。0123456789</p></div>
  <p className="hint">立即生效并自动保存。默认 16 px；间距、圆角与控件随字号同比缩放。{loading?'正在读取系统字体…':`已读取 ${fonts.length} 个系统字体。`}</p>
  {error&&<div className="font-error" role="alert">{error}<button type="button" onClick={refresh}>重新读取</button></div>}
 </section>;
}

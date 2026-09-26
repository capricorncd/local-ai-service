import {createContext, useContext} from 'react';
import {Play, Loader2} from 'lucide-react';
import {t} from './i18n';

export const PlaybackContext = createContext<string|null>(null);

export const PlaybackLoadingContext = createContext<string|null>(null);

export function PlaybackMark({source, label, size=14}: {source:string;label?:string;size?:number}) {
  const loading=useContext(PlaybackLoadingContext)===source;
  const active=useContext(PlaybackContext)===source;
  return <>{loading ? <Loader2 size={size} className="spin"/> : active ? <span className="playing-wave" role="img" aria-label={t('播放中')} title={t('播放中')}><i/><i/><i/><i/></span> : <Play size={size}/>} {label !== undefined && (loading?t('正在加载音频…'):active?t('播放中'):label)}</>;
}

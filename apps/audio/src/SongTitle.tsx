import {EditableTitle} from '../../../packages/ui/src/EditableTitle';
import {t} from './i18n';
export function SongTitle({title,unplayed,disabled,save,onError,tag}:{title:string;unplayed:boolean;disabled:boolean;tag?:string;save:(title:string)=>Promise<void>;onError:(error:string)=>void}){
 return <EditableTitle className="song-title" title={title} save={save} disabled={disabled} onError={onError} maxLength={120} label={t('歌名')} labels={{edit:t('重命名'),save:t('保存'),cancel:t('取消')}} prefix={tag?<span className={'song-tag song-title-tag'+(unplayed?' unplayed':'')} title={unplayed?t('尚未播放'):undefined} aria-label={unplayed?tag+' · '+t('尚未播放'):tag}>{tag}</span>:unplayed?<span className="unplayed-dot" role="img" aria-label={t('尚未播放')} title={t('尚未播放')}/>:undefined}/>;
}

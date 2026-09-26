import {InfoTip as SharedInfoTip} from '../../../packages/ui/src/Dialog';
import {t} from './i18n';
export function InfoTip({text,inline=false}:{text:string;inline?:boolean}){return <SharedInfoTip text={text} inline={inline} label={t('说明')}/>;}

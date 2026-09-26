import {invoke, isTauri} from '@tauri-apps/api/core';
import {RevealFileAction} from '../../../packages/ui/src/index';
import {t} from './i18n';
export function RevealFileButton({path}: {path?:string}) {
  if(!isTauri())return null;
  return <RevealFileAction path={path} reveal={path=>invoke('reveal_file',{path})} label={t('打开文件夹')} title={t('打开所在目录并选中文件')} errorText={error=>t('无法定位文件：{0}',t(String(error)))}/>;
}

import {isTauri} from '@tauri-apps/api/core';
import {getCurrentWindow} from '@tauri-apps/api/window';
import {getUIPreferences} from './uiPreferences';
export async function applyStartupWindow(){
 if(isTauri()&&getUIPreferences().maximizeOnStart)await getCurrentWindow().maximize();
}

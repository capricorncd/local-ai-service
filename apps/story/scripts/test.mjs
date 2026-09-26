import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const python=fileURLToPath(new URL('../../../runtimes/image/Scripts/python.exe',import.meta.url));
// Resolve from the app directory instead of depending on the caller's shell.
const app=fileURLToPath(new URL('../',import.meta.url));
const result=spawnSync(python,['-m','pytest','tests','-q'],{cwd:app,stdio:'inherit',windowsHide:true});
if(result.error)console.error(result.error.message);
process.exit(result.status??1);

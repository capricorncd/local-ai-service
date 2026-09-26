import {useState,type ButtonHTMLAttributes,type ReactNode} from 'react';
import {FolderOpen,Loader2,X} from 'lucide-react';

export function Button({variant='light',className='',children,...props}:ButtonHTMLAttributes<HTMLButtonElement>&{variant?:'light'|'primary';children:ReactNode}) {
  return <button type="button" className={`button ${variant} ${className}`} {...props}>{children}</button>;
}
export function Panel({title,children,className=''}:{title?:ReactNode;children:ReactNode;className?:string}) {
  return <section className={`panel ${className}`}>{title&&<h2>{title}</h2>}{children}</section>;
}
export function Toast({children,close}:{children:ReactNode;close:()=>void}) {
  return <div className="toast" role="status"><span>{children}</span><button type="button" aria-label="Close" onClick={close}><X size={16}/></button></div>;
}
export function RevealFileAction({path,reveal,label,title,errorText}:{path?:string;reveal:(path:string)=>Promise<unknown>;label:string;title:string;errorText:(error:unknown)=>string}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  if(!path)return null;
  return <><Button disabled={busy} title={title} onClick={async()=>{setBusy(true);setError('');try{await reveal(path);}catch(e){setError(errorText(e));}finally{setBusy(false);}}}>{busy?<Loader2 size={14} className="spin"/>:<FolderOpen size={14}/>} {label}</Button>{error&&<span className="song-error" role="alert">{error}</span>}</>;
}

export {AppearanceSettings} from './AppearanceSettings';
export {initializeTheme} from './theme';

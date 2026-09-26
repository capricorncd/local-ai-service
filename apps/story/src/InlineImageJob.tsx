import {Media} from './components';
import {isImagePending} from './imageJobs';
import type {Job} from './types';
export function InlineImageJob({pid,job,error,onCancel,onApply,onDownload,applied=false,compact=false}:{pid:string;job?:Job;error?:string;onCancel:(job:Job)=>void;onApply?:(job:Job)=>void;onDownload:(job:Job)=>void;applied?:boolean;compact?:boolean}){
 if(!job&&!error)return null;
 const pending=isImagePending(job),progress=Math.min(100,Math.max(0,job?.progress||0));
 if(compact){
  const message=error||job?.error||job?.sync_error;
  if(job?.status==='completed'&&!message)return null;
  const label=message?'生成异常':pending?(job?.status==='queued'?'排队中':'生成中')+' '+Math.round(progress)+'%':job?.status==='cancelled'?'已取消':'生成失败';
  return <div className="shot-image-status" role={message?'alert':'status'} title={message||label}><span>{label}</span>{pending&&job&&<button title="取消生成" aria-label="取消生成" onClick={()=>onCancel(job)}>×</button>}</div>;
 }
 return <div className="inline-image-job" aria-live="polite">{job&&<><div className="inline-job-status"><span>{({queued:'排队中',running:'生成中',completed:applied?'已完成 · 已应用':'生成完成',failed:'生成失败',cancelled:'已取消'} as Record<string,string>)[job.status]||job.status}</span>{pending&&<b>{Math.round(progress)}%</b>}</div>{pending&&<progress aria-label="分镜图生成进度" max={100} value={progress}/>}<>{job.path&&!applied&&onApply&&<Media pid={pid} path={job.path}/>}</><div className="actions">{pending&&<button onClick={()=>onCancel(job)}>取消生成</button>}{job.path&&<>{job.kind!=='shot'&&<button onClick={()=>onDownload(job)}>下载</button>}{!applied&&onApply&&<button className="primary" onClick={()=>onApply(job)}>应用到镜头</button>}</>}</div>{job.error&&<p className="warning">{job.error}</p>}{job.sync_error&&<p className="warning">状态读取失败，正在重试：{job.sync_error}</p>}</>}{error&&<p className="warning" role="alert">{error}</p>}</div>;
}
export function BoardImageJob({pid,job,error,onCancel,onDownload}:{pid:string;job?:Job;error?:string;onCancel:(job:Job)=>void;onDownload:(job:Job)=>void}){if(!job&&!error)return null;return <section className="board-image-job"><h2>连续故事板</h2>{job?.path&&<Media pid={pid} path={job.path}/>}<InlineImageJob pid={pid} job={job} error={error} onCancel={onCancel} onDownload={onDownload}/></section>;}

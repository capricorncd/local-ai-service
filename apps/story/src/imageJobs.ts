import type {Job,Project} from './types';
export const isImagePending=(job?:Job)=>!!job&&['queued','running'].includes(job.status);
export const latestImageJob=(jobs:Job[],kind:'shot'|'board',id:string)=>jobs.find(j=>j.kind===kind&&j.target_id===id);
export function applyFinishedShot(project:Project,job:Job,jobs:Job[]){
 if(job.kind!=='shot'||job.status!=='completed'||!job.path||latestImageJob(jobs,'shot',job.target_id)?.id!==job.id)return false;
 const shot=project.chapters.flatMap(c=>c.episodes).flatMap(e=>e.shots).find(s=>s.id===job.target_id);
 if(!shot||shot.image===job.path)return false;
 // A manually imported image or newer result must not be replaced by a late job.
 if(job.previous_image!==undefined&&shot.image!==job.previous_image)return false;
 shot.images=[...new Set([shot.image,...(shot.images||[]),job.path].filter(Boolean))];
 shot.image=job.path;return true;
}

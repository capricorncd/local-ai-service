import {newShot,uid,type Episode} from './types';
export function insertShot(episode:Episode,target:string,position:'before'|'after',copy:boolean,images:string[]=[]){
 const index=episode.shots.findIndex(s=>s.id===target);if(index<0)return false;
 const original=episode.shots[index];const next=copy?{...structuredClone(original),id:uid(),images:[...images]}:newShot();
 episode.shots.splice(index+(position==='after'?1:0),0,next);return true;
}

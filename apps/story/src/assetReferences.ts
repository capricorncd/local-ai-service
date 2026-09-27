import type {Project} from './types';
import {mentionParts} from './mentionText';

export function syncAssetReferences(project:Project,previous:Project){
 const current=new Map(project.assets.map(a=>[a.id,a]));
 const rewrite=(text:string)=>mentionParts(text,previous.assets).map(part=>{
  const old=part.asset,next=old&&current.get(old.id);
  if(!old||!next)return part.text;
  if(!part.text.startsWith('@[')&&(old.name===next.name||previous.assets.filter(a=>a.name===old.name).length!==1))return part.text;
  return `@[${next.name}](asset:${next.id})`;
 }).join('');
 project.style=rewrite(project.style);
 for(const asset of project.assets){
  asset.description=rewrite(asset.description);asset.constraints=rewrite(asset.constraints);
  for(const skill of asset.skills??[]){skill.description=rewrite(skill.description);skill.video_prompt=rewrite(skill.video_prompt);}
 }
 for(const chapter of project.chapters)for(const episode of chapter.episodes){
  episode.script=rewrite(episode.script);
  for(const shot of episode.shots){
   for(const key of ['description','scene','dialogue','sound','subtitle'] as const)shot[key]=rewrite(shot[key]);
   const matches=previous.assets.filter(a=>a.name===shot.speaker);
   if(matches.length===1)shot.speaker=current.get(matches[0].id)?.name??shot.speaker;
  }
 }
}

import type {Asset} from './types';
export type MentionPart={text:string;asset?:Asset};
export function mentionParts(value:string,assets:Asset[]):MentionPart[]{
 const parts:MentionPart[]=[];const names=[...assets].sort((a,b)=>b.name.length-a.name.length);let plain='';
 for(let i=0;i<value.length;){if(value[i]==='@'){const explicit=value.slice(i).match(/^@\[([^\]]*)\]\(asset:([^)]*)\)/);const asset=explicit?assets.find(a=>a.id===explicit[2]):names.find(a=>a.name&&value.startsWith('@'+a.name,i));const token=explicit?.[0]||(asset?'@'+asset.name:'');if(asset&&token){if(plain){parts.push({text:plain});plain='';}parts.push({text:token,asset});i+=token.length;continue;}if(explicit){plain+=explicit[0];i+=explicit[0].length;continue;}}plain+=value[i++];}if(plain)parts.push({text:plain});return parts;
}
export const mentionIds=(value:string,assets:Asset[])=>[...new Set(mentionParts(value,assets).flatMap(p=>p.asset?[p.asset.id]:[]))];
export const removeAssetMention=(value:string,assets:Asset[],id:string)=>mentionParts(value,assets).filter(p=>p.asset?.id!==id).map(p=>p.text).join('');

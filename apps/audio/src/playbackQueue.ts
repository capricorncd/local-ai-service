export type PlaybackMode = 'sequence'|'single'|'list';
export type PlaybackTrack = {url:string;name:string};

export function nextTrack(queue:PlaybackTrack[],current:string,mode:PlaybackMode):PlaybackTrack|null {
  const index=queue.findIndex(track=>track.url===current);
  if(index<0)return null;
  if(mode==='single')return queue[index];
  return queue[index+1]||(mode==='list'?queue[0]:null);
}

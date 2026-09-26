export type Layer={id:string;name:string;source:string;width:number;height:number;x:number;y:number;scale:number;opacity:number;visible:boolean;locked:boolean;reference:boolean};
export type Mode='text'|'continue'|'transparent'|'extract'|'panorama'|'fidelity'|'brush'|'circle'|'mask'|'alpha'|'multi';
export type Project={format:'local-ai-image';version:1;name:string;width:number;height:number;layers:Layer[];active:string|null;mask:string|null;prompt:string;negative:string;mode:Mode;steps:number;cfg:number;seed:number};
export const modes:Record<Mode,string>={text:'文生图',continue:'继续创作',transparent:'透明 PNG',extract:'主体提取',panorama:'全景图',fidelity:'人物 / 产品保真',brush:'涂抹编辑',circle:'圈选编辑',mask:'独立遮罩',alpha:'透明图编辑',multi:'多图编辑'};
export const emptyProject=():Project=>({format:'local-ai-image',version:1,name:'未命名工程',width:1024,height:1024,layers:[],active:null,mask:null,prompt:'',negative:'',mode:'text',steps:30,cfg:4,seed:-1});
export function parseProject(value:unknown):Project{
  const p=value as Project;
  if(!p||p.format!=='local-ai-image'||p.version!==1||typeof p.name!=='string'||!Array.isArray(p.layers)||p.layers.length>50||!(p.mode in modes))throw Error('无效的工程文件或版本不受支持');
  const validNumber=(n:unknown,min:number,max:number)=>typeof n==='number'&&Number.isFinite(n)&&n>=min&&n<=max;
  if(![p.width,p.height].every(n=>validNumber(n,256,2048)&&n%32===0)||p.width*p.height>2097152)throw Error('画布大小无效');
  if(typeof p.prompt!=='string'||p.prompt.length>12000||typeof p.negative!=='string'||p.negative.length>4000||!validNumber(p.steps,1,80)||!Number.isInteger(p.steps)||!validNumber(p.cfg,1,10)||!validNumber(p.seed,-1,2**32-1)||!Number.isInteger(p.seed))throw Error('工程参数无效');
  const data=(s:unknown)=>typeof s==='string'&&s.length<45_000_000&&/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(s);
  const ids=new Set<string>();
  for(const l of p.layers){
    if(typeof l.id!=='string'||ids.has(l.id)||typeof l.name!=='string'||!data(l.source)||![l.width,l.height].every(n=>validNumber(n,1,20000))||l.width*l.height>20_000_000||![l.x,l.y].every(n=>validNumber(n,-20000,20000))||!validNumber(l.scale,.01,20)||!validNumber(l.opacity,0,1)||![l.visible,l.locked,l.reference].every(v=>typeof v==='boolean'))throw Error('工程图层无效');
    ids.add(l.id);
  }
  if(p.mask!==null&&!data(p.mask))throw Error('遮罩数据无效');
  if(p.active!==null&&!ids.has(p.active))throw Error('选中图层不存在');
  return p;
}
export const loadImage=(src:string)=>new Promise<HTMLImageElement>((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(Error('图片读取失败'));image.src=src;});
export const dataURL=(file:Blob)=>new Promise<string>((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result));r.onerror=()=>reject(Error('文件读取失败'));r.readAsDataURL(file);});
export async function renderLayers(p:Project,layers:Layer[]){
  const c=document.createElement('canvas');c.width=p.width;c.height=p.height;const ctx=c.getContext('2d')!;
  for(const l of layers){if(!l.visible)continue;const image=await loadImage(l.source);ctx.globalAlpha=l.opacity;ctx.drawImage(image,l.x,l.y,l.width*l.scale,l.height*l.scale);}
  return c;
}
export const canvasBlob=(canvas:HTMLCanvasElement)=>new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error('画布导出失败')),'image/png'));

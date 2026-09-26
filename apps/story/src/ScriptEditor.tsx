import {InfoTip} from '../../../packages/ui/src/Dialog';
import {FilePenLine,Code2} from 'lucide-react';
import type {ReactNode} from 'react';
import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {Crepe} from '@milkdown/crepe';
import {editorViewCtx,parserCtx,serializerCtx} from '@milkdown/kit/core';
import {$prose,replaceAll} from '@milkdown/kit/utils';
import {Plugin} from '@milkdown/kit/prose/state';
import {Slice} from '@milkdown/kit/prose/model';
import '@milkdown/crepe/theme/common/style.css';
import '@milkdown/crepe/theme/frame.css';
import './ScriptEditor.css';

export type ScriptSelection={text:string;replace:(text:string)=>string};
export type ScriptEditorHandle={getSelection:()=>ScriptSelection|undefined};
type Props={heading?:ReactNode;actions?:ReactNode;value:string;onChange:(value:string)=>void;onSelection:(range:{start:number;end:number})=>void};
export const ScriptEditor=forwardRef<ScriptEditorHandle,Props>(function ScriptEditor(props,ref){
 const host=useRef<HTMLDivElement>(null),crepe=useRef<Crepe|null>(null),latest=useRef(props),emitted=useRef(props.value),syncing=useRef(false);
 const [source,setSource]=useState(false),[error,setError]=useState(''),[ready,setReady]=useState(false);
 const sourceRange=useRef({start:0,end:0});latest.current=props;
 useImperativeHandle(ref,()=>({getSelection(){
  if(source){const {start,end}=sourceRange.current;const text=latest.current.value;return end>start?{text:text.slice(start,end),replace:(replacement:string)=>text.slice(0,start)+replacement+text.slice(end)}:undefined;}
  if(!ready||!crepe.current)return;
  return crepe.current.editor.action(ctx=>{
   const {state}=ctx.get(editorViewCtx),{from,to,empty}=state.selection;
   if(empty)return;
   const serialize=ctx.get(serializerCtx),parse=ctx.get(parserCtx);
   return {text:serialize(state.doc.type.create(null,state.selection.content().content)),replace:(text:string)=>{
    const doc=parse(text);if(!doc)throw new Error('无法解析修订内容');
    return serialize(state.tr.replaceRange(from,to,Slice.maxOpen(doc.content)).doc);
   }};
  });
 }}),[source,ready]);
 useEffect(()=>{
  if(source||!host.current)return;
  let disposed=false;setReady(false);setError('');emitted.current=latest.current.value;
  const editor=new Crepe({root:host.current,defaultValue:latest.current.value,features:{[Crepe.Feature.ImageBlock]:false,[Crepe.Feature.Latex]:false,[Crepe.Feature.CodeMirror]:false,[Crepe.Feature.AI]:false},featureConfigs:{[Crepe.Feature.Placeholder]:{text:'写下第一个镜头，或粘贴 Markdown 剧本…'}}});
  editor.editor.use($prose(ctx=>new Plugin({view:()=>({update(view,previous){
   if(disposed||syncing.current)return;
   if(!view.state.doc.eq(previous.doc)){
    const markdown=ctx.get(serializerCtx)(view.state.doc);
    emitted.current=markdown;latest.current.onChange(markdown);
   }
   if(!view.state.selection.eq(previous.selection)||!view.state.doc.eq(previous.doc)){
    const {from,to}=view.state.selection;
    latest.current.onSelection({start:0,end:view.state.doc.textBetween(from,to,'\n').length});
   }
  }})})));
  const creating=editor.create().then(()=>{if(disposed)return editor.destroy();crepe.current=editor;setReady(true);}).catch(e=>{if(!disposed){setError(String(e));setSource(true);}});
  return()=>{disposed=true;crepe.current=null;void creating.then(()=>editor.destroy()).catch(()=>{});};
 },[source]);
 useEffect(()=>{
  if(!ready||!crepe.current||source||props.value===emitted.current)return;
  syncing.current=true;
  try{crepe.current.editor.action(replaceAll(props.value));emitted.current=props.value;latest.current.onSelection({start:0,end:0});}
  finally{syncing.current=false;}
 },[props.value,source,ready]);
 function mode(next:boolean){sourceRange.current={start:0,end:0};props.onSelection(sourceRange.current);setSource(next);}
 return <div className="story-script-editor"><div className="script-header">{props.heading&&<span className="script-heading">{props.heading}</span>}<div className="script-mode" role="group" aria-label="正文编辑模式"><button type="button" aria-label="可视化编辑" title="可视化编辑" aria-pressed={!source} onClick={()=>mode(false)}><FilePenLine size={17}/></button><button type="button" aria-label="Markdown 源码" title="Markdown 源码" aria-pressed={source} onClick={()=>mode(true)}><Code2 size={17}/></button></div><InfoTip text={source?'直接编辑 Markdown':'选中文字设置格式 · / 插入内容'}/>{props.actions&&<div className="script-header-actions">{props.actions}</div>}</div>{error&&<p className="editor-error">可视化编辑器加载失败，已切换源码：{error}</p>}{source?<textarea aria-label="Markdown 剧本源码" className="script-editor script-source" value={props.value} onChange={e=>props.onChange(e.target.value)} onSelect={e=>{sourceRange.current={start:e.currentTarget.selectionStart,end:e.currentTarget.selectionEnd};props.onSelection(sourceRange.current);}}/>:<><div ref={host} className="script-rich"/>{!ready&&<p className="editor-loading">正在加载编辑器…</p>}</>}</div>;
});

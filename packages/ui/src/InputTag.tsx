import {useRef,useState,type ReactNode} from 'react';
import {X,CircleX} from 'lucide-react';
import './input-tag.css';

export type InputTagProps={value:string[];onChange:(value:string[])=>void;label?:string;placeholder?:string;clearable?:boolean;clearIcon?:ReactNode;disabled?:boolean;readOnly?:boolean;className?:string};
export function InputTag({value,onChange,label='标签',placeholder='输入标签，回车添加',clearable=false,clearIcon,disabled=false,readOnly=false,className=''}:InputTagProps){
 const [text,setText]=useState('');const input=useRef<HTMLInputElement>(null);const composing=useRef(false);
 const locked=disabled||readOnly;
 const add=()=>{if(locked)return;const tag=text.trim();if(!tag)return;if(!value.includes(tag))onChange([...value,tag]);setText('');};
 return <div className={'ui-input-tag '+className} data-disabled={disabled||undefined} onClick={event=>{if(event.target===event.currentTarget&&!disabled)input.current?.focus();}}><div className="ui-input-tag-content">{value.map((tag,index)=><span className="ui-input-tag-item" key={index}><span>{tag}</span>{!readOnly&&<button type="button" disabled={disabled} aria-label={'删除标签：'+tag} onClick={()=>{if(!locked)onChange(value.filter((_,i)=>i!==index));input.current?.focus();}}><X size=".875rem"/></button>}</span>)}<input ref={input} aria-label={label} placeholder={placeholder} value={text} disabled={disabled} readOnly={readOnly} onChange={event=>setText(event.target.value)} onCompositionStart={()=>{composing.current=true;}} onCompositionEnd={()=>{composing.current=false;}} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();if(!composing.current&&!event.nativeEvent.isComposing&&event.keyCode!==229)add();}}}/></div>{clearable&&!locked&&(value.length>0||text.length>0)&&<button type="button" className="ui-input-tag-clear" aria-label="清空所有标签" onClick={()=>{if(value.length)onChange([]);setText('');input.current?.focus();}}>{clearIcon??<CircleX size="1rem"/>}</button>}</div>;
}

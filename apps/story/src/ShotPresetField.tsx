import {useId,useState} from 'react';
// Terminology references:
// https://www.adobe.com/creativecloud/video/production/cinematography/camera-shots-and-angles.html
// https://www.adobe.com/creativecloud/video/discover/low-key-vs-high-key-lighting.html
export const shotPresets={
 shot_size:['大远景','远景','全景','中全景','中景','中近景','近景','特写','大特写'],
 angle:['平视','俯拍','仰拍','顶视（鸟瞰）','贴地仰拍','倾斜角度（荷兰角）','过肩视角','主观视角（POV）'],
 camera_move:['固定','轻推','缓慢推进','快速推进','缓慢拉远','快速拉远','向左摇镜','向右摇镜','向上摇镜','向下摇镜','横向移镜','跟拍','环绕','升降','手持微晃','甩镜','变焦推近','变焦拉远','滑动变焦'],
 lighting:['自然光','柔光','硬光','顺光','侧光','逆光','顶光','底光','轮廓光','三点布光','高调光（明亮低反差）','低调光（暗部高反差）','黄金时刻暖光','月光','窗边柔光']
} as const;
export function ShotPresetField({field,label,value,onChange}:{field:keyof typeof shotPresets;label:string;value:string;onChange:(value:string)=>void}){
 const id=useId();const [custom,setCustom]=useState(false);const choices:readonly string[]=shotPresets[field];const isCustom=custom||!!value&&!choices.includes(value);
 return <div className="shot-preset-field"><label htmlFor={id}>{label}</label><select id={id} value={isCustom?'__custom__':value} onChange={event=>{const next=event.target.value;if(next==='__custom__'){setCustom(true);return;}setCustom(false);onChange(next);}}><option value="">未设置</option>{choices.map(option=><option key={option} value={option}>{option}</option>)}<option value="__custom__">自定义…</option></select>{isCustom&&<input aria-label={label+'（自定义）'} value={value} placeholder={'输入自定义'+label} onChange={event=>onChange(event.target.value)}/>}</div>;
}

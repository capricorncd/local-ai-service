// Map only known validation messages; unrelated runtime failures stay in the summary.
export function configFieldIssues(service:string,message:string):Record<string,string>{
 const result:Record<string,string>={};
 for(const issue of message.split('；').map(value=>value.trim()).filter(Boolean)){
  let field='';
  const explicit=issue.match(/^(model_dir|clone_model_dir):/);
  if(explicit)field=explicit[1];
  else if(issue==='Python 解释器不存在'||issue==='TTS 共用 Python 环境未安装')field='python';
  else if(issue==='请配置输出目录')field='output_dir';
  else if(issue==='请选择存在的音效目录')field='directory';
  else if(issue==='请配置 SQLite 数据库路径')field='database';
  else if(issue==='YuE2 权重文件不存在')field='model_path';
  else if(issue.startsWith('运行目录缺少 YuE2')||issue==='缺少 Seed-VC 运行代码')field='runtime_dir';
  else if(service==='auk'&&/^(缺少完整 Qwen2.5-Omni-3B|Qwen2.5-Omni-3B 权重|Qwen 模型索引)/.test(issue))field='qwen_dir';
  else if(/^(AuK 目录需要|需要完整的 MOSS-SoundEffect|MOSS-SoundEffect 模型文件|缺少 MOSS-SoundEffect 音频解码器|模型目录缺少 last_best_checkpoint|last_best_checkpoint 指向|Seed-VC 模型目录)/.test(issue))field='model_dir';
  else if(issue==='Breeze 推理代码目录不存在')field='breeze_runtime_dir';
  else if(issue.startsWith('Breeze 模型'))field='breeze_model_dir';
  else if(issue==='请配置 Breeze 输出目录')field='breeze_output_dir';
  else if(issue==='FFmpeg 程序不存在')field='ffmpeg';
  if(field)result[field]=[result[field],issue].filter(Boolean).join('；');
 }
 return result;
}

"""Timeline 0.17.23 project v4 / storyboard v1. Portable ZIP includes real media."""
import io
import json
import math
import re
import zipfile
from domain import uid
import image_metadata


def export_timeline(project, episode, store, group_scenes=True):
    media, files, warnings, mapped = [], {}, [], {}
    def register(relative, name, asset=None):
        if not relative: return ''
        if relative in mapped: return mapped[relative]
        path = store.media(project.id, relative)
        id = uid(); mapped[relative] = id
        row = {'id':id, 'kind':'audio' if path.suffix.lower() in ('.wav','.mp3','.ogg','.flac','.m4a') else 'image', 'file':relative, 'location':'input', 'name':name}
        if row['kind'] == 'image':
            record = image_metadata.read(path) if path.suffix.lower() == '.png' else None
            row['generation_prompt'] = (record or {}).get('generation_prompt') or ''
            row['setting_description'] = (record or {}).get('setting_description') or (asset.description if asset else '')
            constraints = (record or {}).get('consistency_constraints') or ([asset.constraints] if asset and asset.constraints else [])
            if constraints: row['setting_description'] += '\n' + '；'.join(constraints)
        package_path='media/'+('images' if row['kind']=='image' else 'audios')+'/'+path.name
        row['file']=package_path
        files[package_path] = path
        media.append(row)
        return id
    assets = {a.id:a for a in project.assets}
    groups, rows = [], []
    for s in episode.shots:
        description = s.description
        for a in project.assets: description = description.replace(f'@[{a.name}](asset:{a.id})', a.name).replace('@'+a.name, a.name)
        row = {k:getattr(s,k) for k in ('id','title','duration','shot_size','camera_move','speaker','dialogue','delivery','emotion','disabled')}
        row.update(description='；'.join(v for v in (s.scene, description, s.angle, s.lighting, ('音效：'+s.sound) if s.sound else '', ('画面文字：'+s.subtitle) if s.subtitle else '') if v), image_id=register(s.image,s.title), clip_ids=[])
        rows.append(row)
        if s.disabled: continue
        if group_scenes and groups and s.scene and groups[-1][-1][0].scene == s.scene:
            groups[-1].append((s,row))
        else: groups.append([(s,row)])
    clips, subtitles, audio_clips, frames = [], [], [], 0
    ms = lambda f: math.floor(f * 1000 / project.fps + .5)
    for group in groups:
        clip_id = uid(); start = frames; mids, definitions, retention = [], [], []
        visual_assets = []
        for s, _ in group:
            for aid in s.asset_ids:
                if aid not in visual_assets: visual_assets.append(aid)
        labels, picture = {}, 0
        for aid in visual_assets:
            a = assets[aid]
            mid = register(a.image, a.name, a)
            if not mid:
                warnings.append(f'资产「{a.name}」尚无设定图，只保留文字描述'); continue
            picture += 1; mids.append(mid); label = f'<Subject {picture}>'; labels[a.name] = label
            desc = next(m['setting_description'] for m in media if m['id'] == mid) or a.description or a.name
            definitions.append(f'{label} 是 <Picture {picture}> 中的{a.name}，{desc}')
            retention.append(f'{label}: fully_preserved - 保持主体身份、服装与材质。')
        for s, row in group:
            if row['image_id'] and row['image_id'] not in mids:
                picture += 1; mids.append(row['image_id'])
                n = group.index((s,row))+1
                definitions.append(f'<Picture {picture}> 是 [Shot {n}] 的分镜构图参考。')
                retention.append(f'<Picture {picture}>: partially_preserved - 延续该镜构图并执行动作。')
        speakers, audio = {}, 0
        for s,_ in group:
            if s.dialogue and s.speaker not in speakers: speakers[s.speaker] = f'(S{len(speakers)+1})'
        for name, speaker in speakers.items():
            a = next((a for a in project.assets if a.name == name and a.kind == 'character'), None)
            if a and a.voice:
                aid = register(a.voice,a.name+'声音'); mids.append(aid); audio += 1
                definitions.append(f'<Audio {audio}> 是 {labels.get(name,name)} {speaker} 的音色参考，{a.voice_description or "沿用说话人的音色"}。')
                retention.append(f'<Audio {audio}>: reference - 参考音色，台词使用本镜正文。')
        body, sounds = [], []
        for n,(s,row) in enumerate(group,1):
            local = (frames-start)/project.fps
            shot_start = frames
            frames += max(1, math.floor(s.duration*project.fps+.5))
            if s.audio:
                if s.audio_text != s.dialogue:
                    warnings.append(f'「{s.title}」配音对应旧对白，未导出过期音频。')
                elif s.audio_duration > s.duration + 1/project.fps:
                    from fastapi import HTTPException
                    raise HTTPException(422,f'「{s.title}」配音长于镜头，请先匹配音频时长，避免截断对白。')
                else:
                    audio_id=register(s.audio,s.speaker+'对白')
                    audio_frames=max(1,math.floor(s.audio_duration*project.fps+.5))
                    duration_ms=ms(shot_start+audio_frames)-ms(shot_start)
                    audio_clips.append({'id':uid(),'type':'audio','name':s.speaker+'对白','enabled':True,'visible':True,'muted':False,'volume':1,
                        'start_ms':ms(shot_start),'duration_ms':duration_ms,'media_ids':[audio_id],
                        'source':{'in_ms':0,'out_ms':duration_ms,'duration_ms':math.floor(s.audio_duration*1000+.5)}})
            timing = '' if n == 1 else f' At {int(local//60):02}:{local%60:06.3f}, '
            desc = row['description']
            for name,label in labels.items(): desc = desc.replace(name,label)
            line = f'[Shot {n}]{timing} {s.shot_size}，{s.camera_move}。{desc}'
            if s.dialogue:
                line += f' {labels.get(s.speaker,s.speaker or "旁白")} {speakers[s.speaker]}，{s.delivery}，{s.emotion}：<d>[Chinese] {s.dialogue}</d>'
                if 'V.O.' in s.delivery or '旁白' in s.delivery: line += ' says in an off-screen voiceover；画面人物嘴唇保持闭合。'
                # No alignment audio exists: sentence intervals are explicit approximations.
                sentences = re.findall(r'[^。！？!?\n]+[。！？!?]?|[^\n]+$', s.dialogue)
                sentences = [x.strip() for x in sentences if x.strip()] or [s.dialogue]
                total = sum(map(len,sentences)); used = 0
                available = frames-shot_start
                if available < len(sentences): sentences = [s.dialogue]; total = len(s.dialogue)
                for i,sentence in enumerate(sentences):
                    first = shot_start + math.floor(used/total*available); used += len(sentence)
                    last = frames if i == len(sentences)-1 else shot_start+math.floor(used/total*available)
                    sub = {'id':uid(),'type':'subtitle','enabled':True,'visible':True,'start_ms':ms(first),'duration_ms':ms(last)-ms(first),'text':sentence}
                    a = next((a for a in project.assets if a.name==s.speaker and a.kind=='character'),None)
                    if a and a.image: sub['character_media_id']=register(a.image,a.name,a)
                    subtitles.append(sub)
            body.append(line)
            if s.sound: sounds.append(s.sound)
            row['clip_ids']=[clip_id]
        prompt = '\n'.join(body)
        if definitions:
            prompt = 'subject_definitions:\n'+'\n'.join(definitions)+'\n\nsummary:\n[reference generation'+(' + audio reference' if audio else '')+'] '+group[0][0].title+'\n\nretention_analysis:\n'+'\n'.join(retention)+'\n\ndetailed_description:\n'+prompt
        else: prompt='integrated_multimodal_description:\n'+prompt
        prompt += '\n\noverall_soundscape:\n'+('；'.join(dict.fromkeys(sounds)) or '仅保留本镜明确描述的实体动作声与对白。')
        clips.append({'id':clip_id,'type':'clip','name':group[0][0].title or '镜头','enabled':True,'visible':True,'muted':False,'volume':1,
            'start_ms':ms(start),'duration_ms':ms(frames)-ms(start),'media_ids':mids,'media_enabled':[True]*len(mids),'prompt':prompt,
            'use_prepend_prompt':True,'use_append_prompt':True,'second_sample':False,'save_latent':False,'clip_role':'multi_ref','agent':'MiniMaxH3'})
    tracks=[{'id':uid(),'type':'director','role':'main','name':'导演','order':0,'enabled':True,'visible':True,'muted':False,'locked':False,'clips':clips}]
    if subtitles:
        tracks.append({'id':uid(),'type':'subtitle','role':'subtitle','name':'对白字幕（估算时序）','order':1,'enabled':True,'visible':True,'muted':False,'locked':False,'clips':subtitles})
        warnings.append('字幕按句长在对应镜头内近似分配，须根据实际配音调整。')
    if audio_clips:
        tracks.append({'id':uid(),'type':'audio','role':'audio','name':'对白配音','order':len(tracks),'enabled':True,'visible':True,'muted':False,'locked':False,'clips':audio_clips})
    result={'project_version':'0.17.23','schema_version':4,'name':project.name+' · '+episode.title,
        'settings':{'fps':project.fps,'width':project.width,'height':project.height,'prepend_prompt':project.style,'append_prompt':'non_diegetic_music:\nn/a.','timeline_zoom':1.2,'current_time':0,'timeline_scroll_left':0,'timeline_scroll_top':0},'media':media,'tracks':tracks}
    return result, {'schema_version':1,'shots':rows}, files, list(dict.fromkeys(warnings))


def bundle(project, storyboard, files, warnings):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,obj in [('project.json',project),('storyboard.json',storyboard)]:
            archive.writestr(name,json.dumps(obj,ensure_ascii=False,indent=2))
        archive.writestr('导出说明.txt','Timeline 0.17.23；工程 schema 4，分镜 schema 1。\n已包含引用素材；通过 Timeline 工程 ZIP 导入。\n'+'\n'.join(warnings))
        for name,path in files.items(): archive.write(path,name)
    return stream.getvalue()

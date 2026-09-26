import logging
import time
import io
import json
import re
import secrets
import wave
import threading
from pathlib import Path
from typing import Literal
import httpx
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from pydantic import BaseModel, Field
from PIL import Image
from domain import Project, Settings, import_script, uid, storyboard_image_size
from storage import Store, atomic_json
from integrations import safe_url, image_headers, checked, run_agent
from timeline import export_timeline, bundle
from agent_api import register_agent_api
import image_metadata


class OpenProject(BaseModel):
    directory: str = ''
    name: str | None = None


class AgentRequest(BaseModel):
    mode: Literal['rewrite','shots']
    content: str = Field(min_length=1,max_length=200000)
    instruction: str = Field(default='',max_length=20000)


class GenerateRequest(BaseModel):
    kind: Literal['asset','shot','board']
    target_id: str
    prompt: str = Field(default='',max_length=10000)
    shot_ids: list[str] = Field(default_factory=list, max_length=9)


class RestoreRequest(BaseModel):
    revision: int


class SpeechRequest(BaseModel):
    shot_id: str
    revision: int = Field(ge=0)
    use_reference: bool = True


def create_app(home: Path):
    store = Store(home)
    token_file = home / 'api-token'
    if not token_file.exists(): token_file.write_text(secrets.token_urlsafe(32))
    token = token_file.read_text().strip()
    app = FastAPI(title='Local AI Story')
    app.state.store = store
    job_locks = {}
    job_lock_guard = threading.Lock()
    def job_lock(pid,jid):
        with job_lock_guard:
            return job_locks.setdefault((pid,jid),threading.RLock())

    @app.middleware('http')
    async def limit(request, next):
        if request.method in ('POST','PUT','PATCH'):
            data=bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data)>100*1024*1024: return JSONResponse({'detail':'文件超过 100 MB'},status_code=413)
            request._body=bytes(data)
        started = time.monotonic()
        logger = logging.getLogger('uvicorn.error')
        try:
            response = await next(request)
        except Exception:
            logger.exception('Story request failed: %s %s (%.0f ms)', request.method, request.url.path, (time.monotonic()-started)*1000)
            return JSONResponse({'detail': f'剧本服务处理失败：{request.method} {request.url.path}。详情见 launcher.log。'}, status_code=500)
        if response.status_code >= 400:
            logger.warning('Story request: %s %s -> %s (%.0f ms)', request.method, request.url.path, response.status_code, (time.monotonic()-started)*1000)
        return response

    app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:1422','http://localhost:1422','http://tauri.localhost','tauri://localhost'],allow_methods=['GET','POST','PUT','PATCH'],allow_headers=['Authorization','Content-Type'])

    def auth(authorization: str=Header(default='')):
        if not secrets.compare_digest(authorization,f'Bearer {token}'): raise HTTPException(401,'认证失败，请填写剧本服务 Token')
    secured=[Depends(auth)]
    @app.get('/v1/system/fonts',dependencies=secured)
    def fonts():
        from system_fonts import system_fonts
        return system_fonts()

    def config():
        p=home/'settings.json'
        return Settings.model_validate_json(p.read_text('utf-8')) if p.exists() else Settings()
    def episode(p,eid):
        for c in p.chapters:
            for e in c.episodes:
                if e.id==eid: return e
        raise HTTPException(404,'话不存在')
    def job_path(pid,jid):
        if not re.fullmatch(r'[a-f0-9]{32}',jid): raise HTTPException(404,'任务不存在')
        return store.root(pid)/'jobs'/f'{jid}.json'

    @app.exception_handler(httpx.HTTPError)
    async def network_error(request, exc):
        return JSONResponse({'detail':'接口连接失败或超时，请检查服务是否启动、地址和模型配置。'},status_code=502)

    @app.get('/health')
    def health(): return {'ok':True,'app':'story'}

    @app.get('/v1/settings',dependencies=secured)
    def get_settings(): return config()

    @app.put('/v1/settings',dependencies=secured)
    def put_settings(settings:Settings):
        safe_url(settings.agent_url); safe_url(settings.image_url,True); safe_url(settings.audio_url,True)
        if settings.project_directory and not Path(settings.project_directory).expanduser().is_absolute():
            raise HTTPException(422, '项目默认目录必须是绝对路径')
        atomic_json(home/'settings.json',settings.model_dump())
        return {'ok':True}

    @app.get('/v1/agent/models',dependencies=secured)
    def models():
        cfg=config(); base=safe_url(cfg.agent_url)
        with httpx.Client(timeout=15,trust_env=False) as client:
            if cfg.provider=='ollama':
                obj=checked(client.get(base+'/api/tags')).json()
                return {'models':[x['name'] for x in obj.get('models',[])]}
            obj=checked(client.get(base+'/models',headers={'Authorization':f'Bearer {cfg.api_key}'})).json()
            return {'models':[x['id'] for x in obj.get('data',[])]}

    @app.get('/v1/projects',dependencies=secured)
    def projects():
        result=[]
        for id,directory in list(store.roots.items()):
            try:
                p=store.load(id)
                result.append({'id':id,'name':p.name,'directory':directory,'updated':p.updated,'episodes':sum(len(c.episodes) for c in p.chapters)})
            except HTTPException:
                result.append({'id':id,'name':Path(directory).name,'directory':directory,'error':'目录不可用','episodes':0,'updated':''})
        return sorted(result,key=lambda p:p['updated'],reverse=True)

    @app.post('/v1/projects/open',dependencies=secured)
    def open_project(req:OpenProject): return store.register(req.directory,req.name,config().project_directory)

    @app.get('/v1/projects/{id}',dependencies=secured)
    def get_project(id:str): return store.load(id)

    @app.put('/v1/projects/{id}',dependencies=secured)
    def save_project(id:str,p:Project): return store.save(id,p)

    @app.post('/v1/import-script',dependencies=secured)
    async def import_text(file:UploadFile):
        if Path(file.filename or '').suffix.lower() not in ('.md','.txt','.markdown'): raise HTTPException(422,'请选择 Markdown 或文本文件')
        data=await file.read()
        if len(data)>2_000_000: raise HTTPException(413,'剧本文件超过 2 MB')
        text=None
        for encoding in ('utf-8-sig','gb18030'):
            try: text=data.decode(encoding); break
            except UnicodeDecodeError: pass
        if text is None: raise HTTPException(422,'无法识别文本编码，请转为 UTF-8')
        return {'chapters':import_script(text,Path(file.filename).stem)}

    @app.get('/v1/skill',dependencies=secured)
    def get_skill():
        from integrations import SKILL
        return {'text':SKILL.read_text('utf-8')}

    @app.post('/v1/projects/{id}/agent',dependencies=secured)
    def agent(id:str,req:AgentRequest):
        p=store.load(id)
        return run_agent(config(),req.mode,req.content,req.instruction,p.assets)

    @app.post('/v1/projects/{id}/media',dependencies=secured)
    async def upload(id:str,file:UploadFile):
        root=store.root(id)
        ext=Path(file.filename or '').suffix.lower()
        if ext not in ('.png','.jpg','.jpeg','.webp','.wav','.mp3','.ogg','.flac','.m4a'): raise HTTPException(422,'仅支持常见图片和音频文件')
        data=await file.read(); metadata=None
        if ext in ('.png','.jpg','.jpeg','.webp'):
            try:
                with Image.open(io.BytesIO(data)) as im:
                    if im.width*im.height>40_000_000: raise ValueError('图片过大')
                    if im.format not in {'PNG','JPEG','WEBP'} or (ext=='.png' and im.format!='PNG'): raise ValueError('扩展名与图片格式不匹配')
                    im.verify()
            except Exception as e: raise HTTPException(422,f'图片无效：{e}')
        relative=f'media/{uid()}{ext}'; path=root/relative
        path.write_bytes(data)
        metadata_warning=''
        if ext=='.png':
            try:
                metadata=image_metadata.read(path)
                if metadata: image_metadata.validate(metadata)
                else:
                    metadata={'schema_version':1,'asset_name':file.filename or path.name,'asset_type':'image','generation_prompt':None,'generation_prompt_status':'unavailable','generation_prompt_source':'历史导入文件没有可靠的原始生成记录','generation_mode':'unknown','reference_images':[]}
                    image_metadata.write(path,metadata,root/'metadata-backups')
            except (ValueError,KeyError,TypeError) as exc:
                metadata=None;metadata_warning=f'保留原图片元数据，未覆盖不兼容记录：{exc}'
        return {'path':relative,'metadata':metadata,'name':file.filename,'metadata_status':(metadata or {}).get('generation_prompt_status','unavailable'),'warning':metadata_warning}

    @app.get('/v1/projects/{id}/media/{name}',dependencies=secured)
    def media(id:str,name:str): return FileResponse(store.media(id,'media/'+name))

    @app.get('/v1/projects/{id}/history',dependencies=secured)
    def versions(id:str):
        return store.versions(id)

    @app.get('/v1/projects/{id}/history/{version}',dependencies=secured)
    def version(id:str,version:str): return store.history(id,version)

    @app.post('/v1/projects/{id}/history/{version}/restore',dependencies=secured)
    def restore(id:str,version:str,req:RestoreRequest):
        p=Project.model_validate(store.history(id,version)['project']); p.revision=req.revision
        return store.save(id,p,'恢复历史版本')

    @app.post('/v1/projects/{id}/generate',dependencies=secured)
    def generate(id:str,req:GenerateRequest):
        p=store.load(id); cfg=config(); base=safe_url(cfg.image_url,True)
        asset=None; selected=[]
        if req.kind=='asset':
            asset=next((a for a in p.assets if a.id==req.target_id),None)
            if not asset: raise HTTPException(404,'资产不存在')
            description='；'.join(v for v in (asset.description,asset.gender,asset.body,asset.form,asset.clothing,asset.constraints) if v)
            if not description.strip(): raise HTTPException(422,'请先填写资产描述')
            prompt=f'{p.style}\n{asset.name}设定图。{description}\n{req.prompt}'.strip()
            refs=[asset] if asset.image else []
        else:
            e=episode(p,req.target_id) if req.kind=='board' else None
            all_shots=[s for c in p.chapters for e2 in c.episodes for s in e2.shots]
            selected=([s for s in e.shots if s.id in req.shot_ids] if e else [s for s in all_shots if s.id==req.target_id])
            if not selected: raise HTTPException(422,'请先选择镜头')
            references=list(dict.fromkeys(aid for s in selected for aid in s.asset_ids))
            refs=[next(a for a in p.assets if a.id==aid) for aid in references]
            prompt=p.style+'\n'
            if req.kind=='board': prompt+=f'连续故事板，共{len(selected)}格，按镜头顺序从左到右、从上到下排列，保持人物服饰、道具和场景一致。\n'
            for n,s in enumerate(selected,1):
                prompt+=f'画面{n}：{s.scene}，{s.shot_size}，{s.angle}，{s.lighting}。{s.description}\n'
            prompt+=req.prompt
        uploaded=[]; reference_records=[]
        with httpx.Client(timeout=60,trust_env=False,headers=image_headers(cfg)) as client:
            for a in refs:
                description=a.description
                constraints=a.constraints
                if a.image:
                    path=store.media(id,a.image)
                    record=image_metadata.read(path) if path.suffix.lower()=='.png' else None
                    if record and record.get('schema_version')==1:
                        description=record.get('setting_description') or description
                        constraints='；'.join(record.get('consistency_constraints',[])) or constraints
                    with path.open('rb') as f:
                        res=checked(client.post(base+'/v1/images',files={'file':(path.name,f)})).json()
                    uploaded.append(res['id'])
                    prompt+=f'\n参考图{len(uploaded)}：{a.name}，{description}；{constraints}'
                    reference_records.append({'filename':a.image,'role':a.kind})
                else: prompt+=f'\n{a.name}：{description}；{constraints}'
            if len(uploaded)>10: raise HTTPException(422,'单次最多引用10张设定图，请减少引用资产')
            for a in p.assets: prompt=prompt.replace(f'@[{a.name}](asset:{a.id})',a.name).replace('@'+a.name,a.name)
            mode='fidelity' if uploaded else 'text'
            width,height=storyboard_image_size(p.width,p.height,cfg.storyboard_max_edge) if req.kind in ('shot','board') else (p.width,p.height)
            payload={'mode':mode,'prompt':prompt.strip(),'references':uploaded,'width':width,'height':height,'steps':cfg.steps,'cfg':cfg.cfg,'seed':-1}
            response=checked(client.post(base+'/v1/jobs',json=payload)).json()
        jid=uid()
        # image application's fidelity mode prepends this exact instruction.
        actual=('Preserve the exact identity, face, product shape, materials, lettering and distinguishing features of the reference subjects.\n' if uploaded else '')+payload['prompt']
        record={'schema_version':1,'asset_name':asset.name if asset else '分镜效果图','asset_type':asset.kind if asset else 'image','generation_prompt':actual,
            'generation_prompt_status':'exact','generation_prompt_source':'Local AI Image /v1/jobs; fidelity prefix included when applicable','generation_mode':'external','reference_images':reference_records}
        if asset:
            record.update(setting_description=description,consistency_constraints=[asset.constraints] if asset.constraints else [],description_source='用户填写的设定描述，生成后须人工核对',observed_differences=[])
        job={'id':jid,'created_at':time.time(),'remote_id':response['id'],'base':base,'kind':req.kind,'target_id':req.target_id,'status':response['status'],'metadata':record,'path':'','prompt':payload['prompt']}
        if req.kind=='shot': job['previous_image']=selected[0].image
        atomic_json(job_path(id,jid),job)
        return job

    @app.get('/v1/projects/{id}/jobs',dependencies=secured)
    def jobs(id:str):
        rows=[(json.loads(path.read_text('utf-8')),path.stat().st_mtime) for path in (store.root(id)/'jobs').glob('*.json')]
        return [job for job,mtime in sorted(rows,key=lambda item:item[0].get('created_at',item[1]),reverse=True)]

    @app.get('/v1/projects/{id}/jobs/{jid}',dependencies=secured)
    def poll(id:str,jid:str):
        path=job_path(id,jid)
        if not path.exists(): raise HTTPException(404,'任务不存在')
        with job_lock(id,jid):
            job=json.loads(path.read_text('utf-8'))
            if job['status'] in ('completed','failed','cancelled'): return job
            cfg=config()
            is_audio=job['kind']=='speech'
            with httpx.Client(timeout=60,trust_env=False,headers=audio_headers() if is_audio else image_headers(cfg)) as client:
                result=checked(client.get(safe_url(job['base'],True)+'/v1/jobs/'+job['remote_id'])).json()
                job['status']='completed' if result['status']=='succeeded' else result['status']; job['progress']=result.get('progress',0)
                if result.get('error'): job['error']=result['error']
                if job['status']=='completed':
                    suffix='/files/0' if is_audio else '/image'
                    blob=checked(client.get(job['base']+'/v1/jobs/'+job['remote_id']+suffix)).content
                    relative=f'media/{jid}'+('.wav' if is_audio else '.png'); target=store.root(id)/relative; target.write_bytes(blob)
                    if is_audio:
                        with wave.open(str(target),'rb') as wav: job['duration']=wav.getnframes()/wav.getframerate()
                    else: image_metadata.write(target,job['metadata'],store.root(id)/'metadata-backups')
                    job['path']=relative
            atomic_json(path,job)
            return job

    @app.post('/v1/projects/{id}/jobs/{jid}/cancel',dependencies=secured)
    def cancel(id:str,jid:str):
        path=job_path(id,jid)
        if not path.exists(): raise HTTPException(404,'任务不存在')
        with job_lock(id,jid):
            job=json.loads(path.read_text('utf-8'))
            if job['status'] in ('completed','failed','cancelled'): return job
            is_audio=job['kind']=='speech'
            with httpx.Client(timeout=20,trust_env=False,headers=audio_headers() if is_audio else image_headers(config())) as client:
                url=safe_url(job['base'],True)+'/v1/jobs/'+job['remote_id']
                result=checked(client.delete(url) if is_audio else client.post(url+'/cancel')).json()
            job['status']=result['status']; atomic_json(path,job); return job

    def audio_headers():
        import os
        cfg=config(); key=cfg.audio_token
        path=Path(os.environ.get('APPDATA',str(Path.home())))/'studio.local-ai.manager/api-token'
        if not key and path.exists(): key=path.read_text().strip()
        if not key: raise HTTPException(409,'请启动音频应用，或填写音频 API Token')
        return {'Authorization':f'Bearer {key}'}

    @app.get('/v1/audio/voices',dependencies=secured)
    def voices():
        with httpx.Client(timeout=20,trust_env=False,headers=audio_headers()) as client:
            return checked(client.get(safe_url(config().audio_url,True)+'/v1/voices')).json()

    @app.post('/v1/projects/{id}/speech',dependencies=secured,tags=['Audio'])
    def speech(id:str,req:SpeechRequest):
        p=store.load(id)
        if p.revision!=req.revision: raise HTTPException(409,'版本已变化，请先重新读取剧本')
        shot=next((s for c in p.chapters for e in c.episodes for s in e.shots if s.id==req.shot_id),None)
        if not shot or not shot.dialogue.strip(): raise HTTPException(422,'镜头没有可朗读的对白')
        if len(shot.dialogue)>2000: raise HTTPException(422,'单条对白最多2000字，请按说话人和语句拆分镜头')
        candidates=[a for a in p.assets if a.kind=='character' and a.name==shot.speaker]
        if len(candidates)>1: raise HTTPException(422,'存在同名角色，请改为唯一名称后配音')
        actor=candidates[0] if candidates else None
        cfg=config();base=safe_url(cfg.audio_url,True);warnings=[]
        payload={'model':cfg.tts_model,'text':shot.dialogue,'language':cfg.tts_language}
        with httpx.Client(timeout=60,trust_env=False,headers=audio_headers()) as client:
            if actor and actor.voice and req.use_reference:
                path=store.media(id,actor.voice)
                with path.open('rb') as f: uploaded=checked(client.post(base+'/v1/uploads',files={'file':(path.name,f)})).json()
                payload.update(reference_upload_id=uploaded['upload_id'],reference_text=actor.voice_reference_text)
                if cfg.tts_model=='breeze-tts2':
                    if not actor.voice_reference_text: raise HTTPException(422,'Breeze 克隆需要填写角色参考录音的准确原文')
                    payload['instruct']='；'.join(v for v in (actor.voice_description,shot.emotion) if v)
                elif shot.emotion: warnings.append('Qwen 参考音色模式不支持 instruct，情绪标签未传入；可改用预设音色或 Breeze。')
            else:
                if cfg.tts_model=='qwen3-tts': payload['speaker']=actor.voice_preset if actor else cfg.tts_speaker
                payload['instruct']='；'.join(v for v in (actor.voice_description if actor else '',shot.emotion) if v) or '自然清晰地朗读'
            remote=checked(client.post(base+'/v1/tts/generate?wait=false',json=payload)).json()
        jid=uid();job={'id':jid,'remote_id':remote['id'],'base':base,'kind':'speech','target_id':shot.id,'status':'queued','path':'','text':shot.dialogue,'speaker':shot.speaker,'duration':0,'warnings':warnings}
        atomic_json(job_path(id,jid),job);return job

    @app.post('/v1/projects/{id}/jobs/{jid}/apply',dependencies=secured,tags=['Agent','Audio'])
    def apply_job(id:str,jid:str,req:RestoreRequest):
        with store.lock:
            path=job_path(id,jid)
            if not path.exists(): raise HTTPException(404,'任务不存在')
            job=json.loads(path.read_text('utf-8'));p=store.load(id)
            if job['status']!='completed' or not job.get('path'): raise HTTPException(409,'任务尚未完成')
            if p.revision!=req.revision: raise HTTPException(409,'项目版本已变化')
            if job['kind']=='asset':
                target=next((a for a in p.assets if a.id==job['target_id']),None)
                if target: target.image=job['path'];target.generation_prompt=job['metadata']['generation_prompt']
            elif job['kind'] in ('shot','speech'):
                target=next((s for c in p.chapters for e in c.episodes for s in e.shots if s.id==job['target_id']),None)
                if target:
                    if job['kind']=='speech':
                        if target.dialogue!=job['text'] or target.speaker!=job['speaker']: raise HTTPException(409,'对白或说话人已改变，请重新生成音频')
                        target.audio=job['path'];target.audio_text=job['text'];target.audio_duration=job['duration']
                    else:
                        target.images=list(dict.fromkeys(filter(None,[target.image,*target.images,job['path']])))
                        target.image=job['path']
            else: raise HTTPException(422,'连续故事板是总览图，请下载查看')
            if target is None: raise HTTPException(404,'生成目标已被删除')
            return store.save(id,p,'应用生成的音频' if job['kind']=='speech' else '应用生成的图片')

    @app.get('/v1/projects/{id}/export/{eid}',dependencies=secured)
    def export(id:str,eid:str,group:bool=True):
        p=store.load(id); e=episode(p,eid)
        if not e.shots: raise HTTPException(422,'当前话还没有分镜')
        result,board,files,warnings=export_timeline(p,e,store,group)
        return Response(bundle(result,board,files,warnings),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="timeline.zip"'})
    register_agent_api(app,store,secured)
    return app

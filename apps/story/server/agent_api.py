"""Scoped CRUD for external agents. Each transaction validates and versions the whole document."""
from typing import Any, Literal
from fastapi import HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from domain import Project, Chapter, Episode, Shot, Asset


class Mutation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0, description='最近读取的项目 revision；过期返回409')
    data: dict[str,Any] = Field(default_factory=dict, description='新增实体或局部更新字段，不能更新 id')
    reason: str = Field(default='Agent 更新', min_length=1,max_length=200)
    actor: str = Field(default='Agent',min_length=1,max_length=80)


class Operation(BaseModel):
    action: Literal['create','update','delete']
    entity: Literal['chapter','episode','shot','asset','project']
    id: str = ''
    parent_id: str = ''
    data: dict[str,Any] = Field(default_factory=dict)


class Transaction(BaseModel):
    revision: int = Field(ge=0)
    reason: str = Field(min_length=1,max_length=200)
    actor: str = Field(default='Agent',min_length=1,max_length=80)
    operations: list[Operation] = Field(min_length=1,max_length=200)


def mutate(project, op):
    models={'chapter':Chapter,'episode':Episode,'shot':Shot,'asset':Asset,'project':Project}
    if op.entity=='project':
        if op.action!='update' or set(op.data)-{'name','width','height','fps','style'}: raise HTTPException(422,'项目局部更新仅支持 name、width、height、fps、style')
        for k,v in op.data.items(): setattr(project,k,v)
        return project.id
    collections={'chapter':[project.chapters],'episode':[c.episodes for c in project.chapters], 'shot':[e.shots for c in project.chapters for e in c.episodes], 'asset':[project.assets]}
    model=models[op.entity]
    if 'id' in op.data or set(op.data)-set(model.model_fields): raise HTTPException(422,'包含未知字段或不可更新的 id')
    if op.action=='create':
        if op.entity=='episode':
            parent=next((c for c in project.chapters if c.id==op.parent_id),None)
            if parent is None: raise HTTPException(404,'父章节不存在')
            collection=parent.episodes
        elif op.entity=='shot':
            parent=next((e for c in project.chapters for e in c.episodes if e.id==op.parent_id),None)
            if parent is None: raise HTTPException(404,'父话不存在')
            collection=parent.shots
        else: collection=collections[op.entity][0]
        entity=model.model_validate(op.data);collection.append(entity);return entity.id
    for collection in collections[op.entity]:
        for i,entity in enumerate(collection):
            if entity.id!=op.id: continue
            if op.action=='delete':
                # Reject dangling asset references instead of silently editing unrelated shots.
                if op.entity=='asset' and any(entity.id in s.asset_ids for c in project.chapters for e in c.episodes for s in e.shots):
                    raise HTTPException(409,'资产仍被镜头引用，请在同一事务中先移除引用')
                collection.pop(i)
            else:
                if op.entity=='asset' and op.data.get('name',entity.name)!=entity.name:
                    new_name=op.data['name']
                    for c in project.chapters:
                        for e in c.episodes:
                            for s in e.shots:
                                if s.speaker==entity.name: s.speaker=new_name
                                if entity.id in s.asset_ids:
                                    s.description=s.description.replace('@'+entity.name,'@'+new_name)
                collection[i]=model.model_validate({**entity.model_dump(),**op.data})
            return entity.id
    raise HTTPException(404,'目标不存在')


def register_agent_api(app, store, secured):
    @app.get('/v1/projects/{id}/content',dependencies=secured,tags=['Agent'])
    def content(id:str,chapter_id:str|None=None,episode_id:str|None=None,include_assets:bool=True):
        p=store.load(id); data=p.model_dump()
        if chapter_id:
            data['chapters']=[c for c in data['chapters'] if c['id']==chapter_id]
            if not data['chapters']: raise HTTPException(404,'章节不存在')
        if episode_id:
            for c in data['chapters']: c['episodes']=[e for e in c['episodes'] if e['id']==episode_id]
            data['chapters']=[c for c in data['chapters'] if c['episodes']]
            if not data['chapters']: raise HTTPException(404,'话不在指定范围内')
        if not include_assets: data.pop('assets')
        return data

    def transaction(id, req):
        with store.lock:
            p=store.load(id)
            if p.revision!=req.revision: raise HTTPException(409,{'message':'版本冲突，请重新读取后合并','current_revision':p.revision})
            try:
                ids=[mutate(p,op) for op in req.operations]
                p=Project.model_validate(p.model_dump())
            except (ValueError,TypeError) as exc: raise HTTPException(422,str(exc))
            result=store.save(id,p,f'{req.actor} · {req.reason}')
            return {'revision':result.revision,'updated':result.updated,'ids':ids,'project':result.model_dump()}

    @app.post('/v1/projects/{id}/transactions',dependencies=secured,tags=['Agent'])
    def transactions(id:str,req:Transaction): return transaction(id,req)

    @app.post('/v1/projects/{id}/chapters',dependencies=secured,tags=['Agent'])
    def add_chapter(id:str,req:Mutation): return single(id,req,'chapter','create')

    @app.post('/v1/projects/{id}/chapters/{chapter}/episodes',dependencies=secured,tags=['Agent'])
    def add_episode(id:str,chapter:str,req:Mutation): return single(id,req,'episode','create',parent=chapter)

    @app.post('/v1/projects/{id}/episodes/{episode}/shots',dependencies=secured,tags=['Agent'])
    def add_shot(id:str,episode:str,req:Mutation): return single(id,req,'shot','create',parent=episode)

    @app.post('/v1/projects/{id}/assets',dependencies=secured,tags=['Agent'])
    def add_asset(id:str,req:Mutation): return single(id,req,'asset','create')

    @app.patch('/v1/projects/{id}/{entity}/{target}',dependencies=secured,tags=['Agent'])
    def update(id:str,entity:Literal['chapters','episodes','shots','assets'],target:str,req:Mutation):
        return single(id,req,{'chapters':'chapter','episodes':'episode','shots':'shot','assets':'asset'}[entity],'update',target)

    def single(id,req,entity,action,target='',parent=''):
        return transaction(id,Transaction(revision=req.revision,reason=req.reason,actor=req.actor,operations=[Operation(action=action,entity=entity,id=target,parent_id=parent,data=req.data)]))

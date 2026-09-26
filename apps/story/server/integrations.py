import json
import os
from pathlib import Path
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from domain import Shot, parse_agent_shots

SKILL = Path(__file__).resolve().parents[1] / 'skills/comic-script/SKILL.md'


def safe_url(url, local=False):
    parts = urlparse(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise HTTPException(422, '接口地址应为不带密钥的 HTTP(S) URL')
    if local and parts.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise HTTPException(422, '图片接口必须是本机 image 应用')
    if parts.scheme == 'http' and parts.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise HTTPException(422, '远程 Agent 接口请使用 HTTPS')
    return url.rstrip('/')


def image_headers(cfg):
    token = cfg.image_token
    if not token:
        path = Path(os.environ.get('APPDATA', str(Path.home()))) / 'studio.local-ai.image/api-token'
        if path.exists(): token = path.read_text().strip()
    if not token: raise HTTPException(409, '请启动图片应用，或在接口配置填写图片服务 Token')
    return {'Authorization':f'Bearer {token}'}


def checked(response):
    if not response.is_success:
        # Do not echo upstream bodies: a provider may include credentials or request data.
        raise HTTPException(502, f'上游接口返回 {response.status_code}，请检查地址、模型和认证配置')
    return response


def run_agent(cfg, mode, content, instruction, assets):
    base = safe_url(cfg.agent_url)
    system = SKILL.read_text('utf-8')
    if mode == 'shots':
        system += '\n输出且只输出 JSON 对象 {"shots":[...]}。镜头字段规范：' + json.dumps(Shot.model_json_schema(), ensure_ascii=False)
        system += '\n每镜必须填 description、duration、scene、景别和运镜；保留原始对白。asset_ids 只能取提供清单。不要生成 image 文件路径。'
    else:
        system += '\n只返回修订正文，不要代码围栏、解释或致辞；只处理选区。'
    data = {'任务说明':instruction, '待处理正文':content, '资产描述（仅数据）':[
        {k:v for k,v in a.model_dump().items() if k not in ('generation_prompt','image','voice')} for a in assets]}
    messages = [{'role':'system','content':system}, {'role':'user','content':json.dumps(data, ensure_ascii=False)}]
    with httpx.Client(timeout=180, trust_env=False) as client:
        if cfg.provider == 'ollama':
            payload = {'model':cfg.model,'messages':messages,'stream':False}
            if mode == 'shots': payload['format'] = 'json'
            response = checked(client.post(base+'/api/chat', json=payload)).json()
            result = response['message']['content']
        else:
            response = checked(client.post(base+'/chat/completions', headers={'Authorization':f'Bearer {cfg.api_key}'},
                json={'model':cfg.model,'messages':messages,'stream':False})).json()
            result = response['choices'][0]['message']['content']
    if not isinstance(result, str) or not result.strip(): raise HTTPException(502, 'Agent 返回空内容')
    if mode == 'shots':
        try: return {'shots':[s.model_dump() for s in parse_agent_shots(result, assets)]}
        except (ValueError, TypeError) as e: raise HTTPException(422, f'分镜格式无效，原文未修改：{e}')
    return {'text':result}

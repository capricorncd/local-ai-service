"""Compile shot references into scoped image instructions without setting-sheet layout leakage."""
import re
from fastapi import HTTPException
import image_metadata

PREFIXES = {
    'fidelity': 'Preserve the exact identity, face, product shape, materials, lettering and distinguishing features of the reference subjects.',
    'multi': 'Use the numbered reference images together according to the instruction, preserving the requested subject identities.',
    'text': '',
}
MENTION = re.compile(r'@\[([^\]]*)\]\(asset:([^)]*)\)')
LAYOUT = re.compile(r'设定图|参考图本身|三视图|四视图|多视图|设定板|白底|白色背景|纯白背景|reference sheet|character sheet|turnaround|white background', re.I)
SCENE_ACTION = re.compile(r'坐在|坐下|站在|双腿|携带|提着|背包|人物|角色')


def text(value):
    return value.strip() if isinstance(value, str) else ''


def role_for(asset):
    if asset.kind == 'character' and re.search(r'路人|群演|背景乘客|背景人物|仅作.{0,8}群体', asset.name + asset.constraints):
        return '背景人物'
    return {'character': '角色', 'scene': '场景', 'prop': '道具'}[asset.kind]


def clean(value, scene=False):
    kept, removed = [], []
    for part in re.split(r'[。；;\n]+', value):
        part = part.strip()
        if not part:
            continue
        if LAYOUT.search(part) or (scene and SCENE_ACTION.search(part)):
            removed.append(part)
        else:
            kept.append(part)
    return '；'.join(kept), removed


def ref_label(ref):
    return ref['label'] + '（文字设定，无参考图）'


def compile_shot_prompt(project, selected, store, kind='shot', extra=''):
    assets = {a.id: a for a in project.assets}
    ids = list(dict.fromkeys(aid for shot in selected for aid in shot.asset_ids))
    warnings = []
    for shot in selected:
        for match in MENTION.finditer(shot.description):
            if match[2] not in assets:
                raise HTTPException(422, f'引用的素材不存在：{match[1]}，请重新选择 @素材')
            if match[2] not in ids:
                ids.append(match[2])
        for asset in sorted(project.assets, key=lambda a: len(a.name), reverse=True):
            if '@' + asset.name in shot.description and asset.id not in ids:
                ids.append(asset.id)
    if any(aid not in assets for aid in ids):
        raise HTTPException(422, '镜头包含失效素材引用，请移除或重新选择')
    references = []
    number = 0
    for aid in ids:
        asset = assets[aid]
        record = None
        if asset.image:
            path = store.media(project.id, asset.image)
            try:
                record = image_metadata.read(path) if path.suffix.lower() == '.png' else None
            except (ValueError, OSError):
                warnings.append(f'{asset.name}：无法读取设定元数据，使用资产文字描述。')
        if not isinstance(record, dict) or record.get('schema_version') != 1:
            record = {}
        # User-maintained asset fields take priority over potentially stale embedded descriptions.
        description = asset.description.strip() or text(record.get('setting_description'))
        constraints = asset.constraints.strip()
        if not constraints:
            values = record.get('consistency_constraints', [])
            constraints = '；'.join(v for v in values if isinstance(v, str)) if isinstance(values, list) else ''
        description = '；'.join(dict.fromkeys(v for v in (description, asset.gender, asset.body, asset.form, asset.clothing) if v))
        description, removed_desc = clean(description, asset.kind == 'scene')
        constraints, removed_rules = clean(constraints, asset.kind == 'scene')
        excluded = removed_desc + removed_rules
        if excluded:
            warnings.append(f'{asset.name}：已隔离设定图排版或场景中的人物动作约束，请在预览中核对。')
        if asset.image:
            number += 1
        references.append({'id': aid, 'name': asset.name, 'kind': asset.kind, 'role': role_for(asset), 'image': asset.image, 'number': number if asset.image else None, 'description': description, 'constraints': constraints, 'excluded': excluded})
    if number > 10:
        raise HTTPException(422, '单次最多引用10张设定图，请减少引用资产')
    if number > 4:
        warnings.append('本镜参考图较多，先核对主体站位；若仍漏人，可先生成主要角色构图，再加入背景群演。')
    role_counts = {}
    for ref in references:
        role_counts[ref['role']] = role_counts.get(ref['role'], 0) + 1
        ref['label'] = ref['role'] + (chr(64 + role_counts[ref['role']]) if ref['role'] == '角色' else str(role_counts[ref['role']]))
    labels = {r['id']: f"{r['label']}（参考图{r['number']} / image {r['number']}）" if r['number'] else ref_label(r) for r in references}
    def expand(value):
        # Resolve stable IDs before names so a renamed asset cannot silently lose its binding.
        placeholders = {}
        def reserve(label):
            key = f'__ASSET_REF_{len(placeholders)}__'
            placeholders[key] = label
            return key
        value = MENTION.sub(lambda match: reserve(labels[match[2]]), value)
        for ref in sorted(references, key=lambda item: len(item['name']), reverse=True):
            value = value.replace('@' + ref['name'], reserve(labels[ref['id']]))
        for key, label in placeholders.items():
            value = value.replace(key, label)
        return value
    lines = ['【生成目标】' + (f'连续故事板，共 {len(selected)} 格，按指定镜头顺序排列。' if kind == 'board' else '生成一张单镜头叙事画面。')]
    lines += ['以【本镜画面与动作】中的人物、姿态、空间关系和道具归属为准。参考图只提供指定素材的外观，不复制设定板排版、白底、多视图或参考场景中的人物站位。', '同一角色的多视图只对应一个人；不同参考图中的角色保持独立身份，不混合脸、发型或服装。人物站位和动作不得被参考图的默认姿势替代。']
    if project.style.strip():
        lines.append('【全局画面风格】' + project.style.strip())
    for index, shot in enumerate(selected, 1):
        lines.append(f'【本镜画面与动作 {index}】{shot.title}')
        camera = '；'.join(f'{key}：{value}' for key, value in [('场景', shot.scene), ('景别', shot.shot_size), ('角度', shot.angle), ('光线', shot.lighting)] if value.strip())
        if camera:
            lines.append(camera)
        if not shot.scene.strip():
            warnings.append(f'{shot.title}：场景题头未填写，输入框中的示例占位文字不会发送给 AI。')
        lines.append(expand(shot.description))
        if shot.camera_move.strip():
            lines.append('运镜意图（静帧不表现运动过程）：' + shot.camera_move)
        present = [ref for ref in references if ref['role'] == '角色' and (ref['id'] in shot.asset_ids or ref['id'] in [m[2] for m in MENTION.finditer(shot.description)])]
        if present:
            lines.append('本镜角色核对：' + '；'.join(labels[ref['id']] for ref in present) + '。按正文逐一安排，避免漏人、身份融合或互相完全遮挡；明确画外角色除外。')
    lines.append('【参考素材映射 · 以下仅限素材外观】')
    for ref in references:
        scope = {'角色': '只参考此人的身份、脸、发型、体型与服装；动作、所持道具及位置由本镜正文决定。', '背景人物': '仅用于背景群演外观；不作为主要角色，也不要求整张设定板的人数或并排站姿。', '场景': '仅参考空间结构、材质和环境；按本镜要求重新构图，可改变观察方向，不复制参考图中的角色和个人物品。', '道具': '仅参考该物品的形状、材质、颜色；持有者、数量与位置以本镜正文为准。'}[ref['role']]
        lines.append(labels[ref['id']] + '｜用途：' + ref['role'] + '。' + scope)
        if ref['description']:
            lines.append('外观：' + ref['description'])
        if ref['constraints']:
            lines.append('外观一致性：' + ref['constraints'])
    if extra.strip():
        lines.append('【本次补充要求】' + extra.strip())
    lines.append('【最终核对】按本镜正文安排每个角色与道具，保留关键站位和遮挡关系；除明确要求外，不输出设定板、人物三视图、标签、水印或字幕。')
    mode = 'multi' if number > 1 else 'fidelity' if number else 'text'
    prompt = '\n'.join(lines)
    if len(prompt) > 20000:
        warnings.append('提示词超过图片接口 20000 字符限制，请精简外观描述或在预览中缩短后提交。')
    return {'prompt': prompt, 'mode': mode, 'prefix': PREFIXES[mode], 'references': references, 'warnings': list(dict.fromkeys(warnings))}

"""Synchronize editable mention labels without changing historical generation records."""
import re


def sync_asset_references(project, previous):
    current = {a.id: a for a in project.assets}
    names = sorted({a.name for a in previous.assets if a.name}, key=len, reverse=True)
    pattern = re.compile(r'@\[([^\]]*)\]\(asset:([^)]*)\)' + (r'|@(' + '|'.join(re.escape(n) for n in names) + ')' if names else ''))

    def rewrite(text):
        def replace(match):
            if match.group(2) is not None:
                asset = current.get(match.group(2))
                return f'@[{asset.name}](asset:{asset.id})' if asset else match.group(0)
            matches = [a for a in previous.assets if a.name == match.group(3)]
            if len(matches) != 1:
                return match.group(0)
            old = matches[0]
            asset = current.get(old.id)
            return f'@[{asset.name}](asset:{asset.id})' if asset and asset.name != old.name else match.group(0)
        return pattern.sub(replace, text)

    project.style = rewrite(project.style)
    for asset in project.assets:
        asset.description = rewrite(asset.description)
        asset.constraints = rewrite(asset.constraints)
        for skill in asset.skills:
            skill.description = rewrite(skill.description)
            skill.video_prompt = rewrite(skill.video_prompt)
    for chapter in project.chapters:
        for episode in chapter.episodes:
            episode.script = rewrite(episode.script)
            for shot in episode.shots:
                for key in ('description', 'scene', 'dialogue', 'sound', 'subtitle'):
                    setattr(shot, key, rewrite(getattr(shot, key)))
                matches = [a for a in previous.assets if a.name == shot.speaker]
                if len(matches) == 1 and matches[0].id in current:
                    shot.speaker = current[matches[0].id].name

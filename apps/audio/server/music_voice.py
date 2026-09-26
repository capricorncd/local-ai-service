"""Apply explicit vocal preference while preserving instrumental requests."""
import re


def vocal_style(request):
    style = request.get('style', '')
    gender = request.get('vocal_gender', 'default')
    lyrics = request.get('lyrics', '').strip()
    if gender not in ('male', 'female') or not lyrics or lyrics.lower() == '[instrumental]':
        return style
    # Remove conflicting vocal directions from presets; preserve musical descriptors.
    parts = re.split(r'[,，;；\n]+', style)
    parts = [part.strip() for part in parts if not re.search(r'\b(vocals?|singing|singer|instrumental|baritone|soprano|tenor|humming|choir)\b|男声|女声|人声|演唱|纯音乐', part, re.I)]
    parts.append('Male lead vocal' if gender == 'male' else 'Female lead vocal')
    return ', '.join(filter(None, parts))

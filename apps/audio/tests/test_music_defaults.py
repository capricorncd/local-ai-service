from server.models import MusicRequest, INSTRUMENTAL_STYLE


def test_blank_lyrics_become_instrumental_and_revalidation_is_stable():
    request = MusicRequest(lyrics=' \n ', style='cinematic strings')
    assert request.lyrics == '[Instrumental]'
    assert request.style == 'cinematic strings, ' + INSTRUMENTAL_STYLE
    assert MusicRequest(**request.model_dump()).model_dump() == request.model_dump()


def test_blank_style_does_not_force_a_genre():
    request = MusicRequest()
    assert request.style == INSTRUMENTAL_STYLE
    assert request.lyrics == '[Instrumental]'
    vocal = MusicRequest(lyrics='[Verse]\nHello', style='  ')
    assert vocal.style == ''
    assert vocal.lyrics == '[Verse]\nHello'


def test_explicit_lyrics_and_style_are_preserved():
    request = MusicRequest(lyrics='[Verse]\nHello', style='folk, female vocal', max_duration=180)
    assert request.style == 'folk, female vocal'
    assert request.lyrics == '[Verse]\nHello'
    assert request.max_duration == 180


def test_model_selection_defaults_and_saved_paths(tmp_path):
    from server.models import MusicConfig
    assert MusicConfig().model_path == ''
    assert MusicConfig().encoder_path == ''
    selected=MusicConfig(model_path=str(tmp_path/'music.safetensors'), encoder_path=str(tmp_path/'encoder.safetensors'))
    assert MusicConfig.model_validate_json(selected.model_dump_json()) == selected

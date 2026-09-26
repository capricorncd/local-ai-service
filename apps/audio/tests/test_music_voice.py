import pytest
from pydantic import ValidationError
from server.models import MusicRequest
from server.music_voice import vocal_style


def test_voice_default_preserves_style():
    request = MusicRequest(style='Jazz, female vocals', lyrics='Hello')
    assert vocal_style(request.model_dump()) == request.style


@pytest.mark.parametrize('gender,expected', [('male','Male lead vocal'),('female','Female lead vocal')])
def test_voice_choice_replaces_conflicting_preset(gender, expected):
    request = MusicRequest(style='Jazz, male vocals, female singing, warm baritone, piano',lyrics='Hello',vocal_gender=gender)
    assert vocal_style(request.model_dump()) == 'Jazz, piano, ' + expected
    assert request.style.startswith('Jazz, male vocals')


def test_instrumental_stays_instrumental_and_request_limits():
    request = MusicRequest(vocal_gender='female')
    assert vocal_style(request.model_dump()) == request.style
    MusicRequest(style='a'*4000,lyrics='b'*20000,vocal_gender='male')
    for params in ({'vocal_gender':'other'}, {'style':'a'*4001,'lyrics':'hello'}, {'lyrics':'b'*20001}):
        with pytest.raises(ValidationError):
            MusicRequest(**params)

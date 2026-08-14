import pytest

from services.stt_transcriber import FallbackTranscriber, TranscriptionError


class _FakeTranscriber:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def transcribe(self, audio_path):
        self.calls += 1
        if self.error:
            raise TranscriptionError(self.error)
        return self.result


def test_fallback_transcriber_uses_primary_when_available():
    primary = _FakeTranscriber(result="пятьсот рублей продукты")
    fallback = _FakeTranscriber(result="fallback")

    assert FallbackTranscriber(primary, fallback).transcribe("voice.ogg") == "пятьсот рублей продукты"
    assert primary.calls == 1
    assert fallback.calls == 0


def test_fallback_transcriber_uses_fallback_when_primary_fails():
    primary = _FakeTranscriber(error="http_503")
    fallback = _FakeTranscriber(result="тысяча рублей кафе")

    assert FallbackTranscriber(primary, fallback).transcribe("voice.ogg") == "тысяча рублей кафе"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_fallback_transcriber_reports_both_errors():
    primary = _FakeTranscriber(error="http_503")
    fallback = _FakeTranscriber(error="empty_transcript")

    with pytest.raises(TranscriptionError) as exc:
        FallbackTranscriber(primary, fallback).transcribe("voice.ogg")
    assert "primary=http_503" in str(exc.value)
    assert "fallback=empty_transcript" in str(exc.value)

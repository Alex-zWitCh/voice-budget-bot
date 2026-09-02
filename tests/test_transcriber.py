import shutil
import subprocess

import pytest

from services.audio_converter import normalize_voice
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


def _audio_duration(path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg/ffprobe not available")
def test_normalize_voice_does_not_truncate_long_recording(tmp_path):
    source = tmp_path / "long.ogg"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=12",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(source),
        ],
        check=True,
    )

    output = normalize_voice(source, tmp_path / "long_normalized.ogg", 16000, "16k")

    assert _audio_duration(output) >= 10.0

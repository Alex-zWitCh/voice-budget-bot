import logging

import requests
import urllib3


logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    pass


class GroqTranscriber:
    def __init__(self, api_key: str, base_url: str, model: str, timeout_sec: int, verify_ssl: bool = True, provider_name: str = "groq"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_sec = timeout_sec
        self.verify_ssl = verify_ssl
        self.provider_name = provider_name
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def transcribe(self, audio_path) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {"model": self.model, "language": "ru", "temperature": "0", "response_format": "json"}
        last_error = None
        for _ in range(2):
            try:
                with open(audio_path, "rb") as audio_file:
                    files = {"file": (audio_path.name, audio_file, "audio/ogg")}
                    response = requests.post(
                        f"{self.base_url}/audio/transcriptions",
                        headers=headers,
                        data=data,
                        files=files,
                        timeout=self.timeout_sec,
                        verify=self.verify_ssl,
                    )
                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = f"http_{response.status_code}"
                    continue
                response.raise_for_status()
                text = (response.json().get("text") or "").strip()
                if not text:
                    raise TranscriptionError("empty_transcript")
                return text
            except (requests.RequestException, ValueError) as exc:
                last_error = str(exc)
        raise TranscriptionError(last_error or "transcription_failed")


class FallbackTranscriber:
    def __init__(self, primary, fallback=None):
        self.primary = primary
        self.fallback = fallback

    def transcribe(self, audio_path) -> str:
        try:
            return self.primary.transcribe(audio_path)
        except TranscriptionError as primary_error:
            if not self.fallback:
                raise
            logger.warning("Primary STT provider failed, trying fallback: %s", primary_error)
            try:
                return self.fallback.transcribe(audio_path)
            except TranscriptionError as fallback_error:
                logger.warning("Fallback STT provider failed: %s", fallback_error)
                raise TranscriptionError(f"primary={primary_error}; fallback={fallback_error}") from fallback_error

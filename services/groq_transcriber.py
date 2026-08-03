import requests


class TranscriptionError(Exception):
    pass


class GroqTranscriber:
    def __init__(self, api_key: str, base_url: str, model: str, timeout_sec: int):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_sec = timeout_sec

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

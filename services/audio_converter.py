import subprocess
from pathlib import Path


class AudioConversionError(Exception):
    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.message = message
        self.stderr = stderr or ""


def normalize_voice(input_path: Path, output_path: Path, sample_rate: int, bitrate: str, timeout_sec: int = 15) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-c:a",
        "libopus",
        "-b:a",
        bitrate,
        "-application",
        "voip",
        str(output_path),
    ]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        stderr = getattr(exc, "stderr", None) or ""
        raise AudioConversionError("ffmpeg_failed", stderr=stderr[-2000:]) from exc
    except subprocess.CalledProcessError as exc:
        raise AudioConversionError("ffmpeg_failed", stderr=(exc.stderr or "")[-2000:]) from exc
    return output_path


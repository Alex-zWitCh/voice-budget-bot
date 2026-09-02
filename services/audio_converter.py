import subprocess
from pathlib import Path


class AudioConversionError(Exception):
    pass


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
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=timeout_sec)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise AudioConversionError("ffmpeg_failed") from exc
    return output_path


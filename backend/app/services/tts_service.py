import subprocess
from pathlib import Path
from typing import Any

from ..config import settings


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        details = (result.stderr or result.stdout)[-3000:]
        raise RuntimeError(f"Lệnh thất bại: {' '.join(command[:3])}\n{details}")


def probe_duration(path: Path) -> float:
    command = [
        settings.FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"Không đọc được thời lượng audio: {result.stderr[-1000:]}")
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"ffprobe trả về thời lượng không hợp lệ cho {path.name}") from exc


class VieNeuTTSService:
    def generate(self, scenes: list[dict[str, Any]], audio_dir: Path, voice: str) -> list[dict[str, Any]]:
        try:
            from vieneu import Vieneu
        except ImportError as exc:
            raise RuntimeError("Chưa cài VieNeu-TTS. Hãy chạy: pip install vieneu") from exc

        audio_dir.mkdir(parents=True, exist_ok=True)
        backend = settings.VIENEU_BACKEND.strip() or "onnx"
        tts = Vieneu(backend=backend)
        outputs: list[dict[str, Any]] = []
        for index, scene in enumerate(scenes, start=1):
            stem = f"scene_{index:03d}"
            wav_path = audio_dir / f"{stem}.wav"
            mp3_path = audio_dir / f"{stem}.mp3"
            audio = tts.infer(scene["narration"], voice=voice)
            tts.save(audio, str(wav_path))
            # The selected speech-to-subtitle aligner pairs transcript files with MP3 files.
            # We also use this exact MP3 in Remotion so the timestamps describe the rendered audio.
            _run([
                settings.FFMPEG_BIN, "-y", "-i", str(wav_path), "-vn",
                "-ac", "1", "-ar", "48000", "-c:a", "libmp3lame", "-b:a", "192k", str(mp3_path),
            ])
            outputs.append({
                "scene_id": scene["id"],
                "wav_path": str(wav_path),
                "mp3_path": str(mp3_path),
                "duration_seconds": probe_duration(mp3_path),
            })
        return outputs


def prepare_uploaded_audio(audio_files: list[dict[str, Any]], project_dir: Path) -> list[dict[str, Any]]:
    audio_dir = project_dir / "audio"
    outputs = []
    for item in audio_files:
        scene_id = int(item["scene_id"])
        source_path = project_dir / item["path"]
        if not source_path.is_file():
            raise RuntimeError(f"Không tìm thấy audio đã upload cho cảnh {scene_id}.")
        mp3_path = audio_dir / f"scene_{scene_id:03d}.mp3"
        _run([
            settings.FFMPEG_BIN, "-y", "-i", str(source_path), "-vn",
            "-ac", "1", "-ar", "48000", "-c:a", "libmp3lame", "-b:a", "192k", str(mp3_path),
        ])
        outputs.append({
            "scene_id": scene_id,
            "mp3_path": str(mp3_path),
            "duration_seconds": probe_duration(mp3_path),
        })
    return outputs

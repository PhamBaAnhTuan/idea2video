import csv
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)


class SpeechToSubtitleAlignmentService:
    """Create word-level timings from generated speech.

    `mai` and `whisper` perform ASR on the audio. `forced_alignment` anchors the
    supplied script text to audio with the repository's MMS aligner.
    """

    def align_scenes(self, scenes: list[dict[str, Any]], audio_items: list[dict[str, Any]],
                     transcript_dir: Path, output_dir: Path) -> dict[int, list[dict[str, Any]]]:
        repo = settings.ALIGNMENT_REPO_DIR
        backend = settings.STT_BACKEND.strip().lower()
        if backend not in {"mai", "whisper", "forced_alignment"}:
            raise RuntimeError(
                f"STT_BACKEND không hợp lệ: {settings.STT_BACKEND}. "
                "Dùng mai, whisper hoặc forced_alignment."
            )
        expected = None
        if backend == "mai":
            expected = repo / "transcribe" / "mai_transcribe" / "run_pipeline.py"
        elif backend == "forced_alignment":
            expected = repo / "realign" / "run_batch.py"
        if expected is not None and not expected.exists():
            raise RuntimeError(
                "Không tìm thấy thành phần speech-to-subtitle cần thiết. Hãy clone repo vào "
                f"{repo} (xem README.md)."
            )
        transcript_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        for index, scene in enumerate(scenes, start=1):
            (transcript_dir / f"scene_{index:03d}.txt").write_text(
                scene["narration"].strip() + "\n", encoding="utf-8"
            )

        if backend == "mai":
            return self._run_mai(scenes, audio_items, transcript_dir, output_dir, repo)
        if backend == "whisper":
            return self._run_whisper(scenes, audio_items, transcript_dir, output_dir)
        if backend == "forced_alignment":
            return self._run_forced_alignment(scenes, audio_items, transcript_dir, output_dir, repo)
        raise AssertionError("Validated STT backend was not dispatched.")

    def _run_whisper(self, scenes, audio_items, transcript_dir, output_dir):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "STT_BACKEND=whisper cần faster-whisper. Cài dependency bằng "
                "backend\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt."
            ) from exc

        model_name = settings.WHISPER_MODEL.strip()
        if not model_name:
            raise RuntimeError("WHISPER_MODEL không được để trống.")
        logger.info(
            "Loading local Whisper model %s (device=%s, compute_type=%s)",
            model_name,
            settings.WHISPER_DEVICE,
            settings.WHISPER_COMPUTE_TYPE,
        )
        try:
            model = WhisperModel(
                model_name,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Không tải/khởi tạo được Whisper model '{model_name}' "
                f"(device={settings.WHISPER_DEVICE}, compute_type={settings.WHISPER_COMPUTE_TYPE}): {exc}"
            ) from exc
        logger.info("Local Whisper model %s is ready", model_name)

        audio_by_id = {int(item["scene_id"]): item for item in audio_items}
        aligned: dict[int, list[dict[str, Any]]] = {}
        for index, scene in enumerate(scenes, start=1):
            scene_id = int(scene["id"])
            audio_path = Path(audio_by_id[scene_id]["mp3_path"]).resolve()
            scene_out = output_dir / "whisper" / f"scene_{index:03d}"
            scene_out.mkdir(parents=True, exist_ok=True)
            log_path = scene_out / "stt.log"
            started = time.perf_counter()
            try:
                logger.info("Whisper transcribing scene %s from %s", scene_id, audio_path.name)
                segments, info = model.transcribe(
                    str(audio_path),
                    language=settings.WHISPER_LANGUAGE.strip() or None,
                    word_timestamps=True,
                    beam_size=5,
                )
                transcript_segments = []
                words = []
                for segment in segments:
                    transcript_segments.append(segment.text.strip())
                    for word in segment.words or []:
                        text = word.word.strip()
                        if text and word.start is not None and word.end is not None:
                            words.append({
                                "w": text,
                                "start": float(word.start),
                                "end": float(word.end),
                                "score": getattr(word, "probability", None),
                            })
                if not words:
                    raise RuntimeError(
                        "Whisper không trả timestamp từng từ. Kiểm tra audio và thử model lớn hơn."
                    )

                transcript = " ".join(part for part in transcript_segments if part)
                (transcript_dir / f"scene_{index:03d}_asr.txt").write_text(
                    transcript + "\n", encoding="utf-8"
                )
                (scene_out / "raw_transcript.txt").write_text(transcript + "\n", encoding="utf-8")
                (scene_out / "whisper_words.json").write_text(
                    json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                elapsed = time.perf_counter() - started
                log_path.write_text(
                    f"backend=faster-whisper\nmodel={model_name}\n"
                    f"language={getattr(info, 'language', settings.WHISPER_LANGUAGE)}\n"
                    f"audio={audio_path}\nwords={len(words)}\nelapsed_seconds={elapsed:.2f}\n",
                    encoding="utf-8",
                )
                aligned[scene_id] = words
                logger.info(
                    "Whisper transcribed scene %s: %s words in %.2fs",
                    scene_id,
                    len(words),
                    elapsed,
                )
            except Exception as exc:
                log_path.write_text(
                    f"backend=faster-whisper\nmodel={model_name}\naudio={audio_path}\n"
                    f"error={type(exc).__name__}: {exc}\n",
                    encoding="utf-8",
                )
                raise RuntimeError(
                    f"Whisper STT thất bại ở cảnh {scene_id}. Xem {log_path}: {exc}"
                ) from exc
        return aligned

    def _run_mai(self, scenes, audio_items, transcript_dir, output_dir, repo):
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError(
                "STT_BACKEND=mai cần OPENROUTER_API_KEY. Tạo key trên OpenRouter và điền "
                "vào backend/.env. Có thể dùng STT_BACKEND=forced_alignment nếu muốn căn chỉnh "
                "script Gemini bằng MMS thay vì nhận diện lại audio."
            )

        audio_by_id = {int(item["scene_id"]): item for item in audio_items}
        aligned: dict[int, list[dict[str, Any]]] = {}
        for index, scene in enumerate(scenes, start=1):
            scene_id = int(scene["id"])
            audio_path = Path(audio_by_id[scene_id]["mp3_path"]).resolve()
            scene_out = output_dir / "mai" / f"scene_{index:03d}"
            scene_out.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env.update({
                "OPENROUTER_API_KEY": settings.OPENROUTER_API_KEY,
                "MAI_MODEL": settings.MAI_MODEL,
                "MAI_LANGUAGE": settings.MAI_LANGUAGE,
                "MAI_WORKERS": str(settings.MAI_WORKERS),
            })
            command = [
                sys.executable, "-m", "transcribe.mai_transcribe.run_pipeline",
                "--input", str(audio_path), "--out-dir", str(scene_out.resolve()),
                "--workers", str(settings.MAI_WORKERS),
            ]
            result = subprocess.run(
                command, cwd=str(repo), env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            (scene_out / "stt.log").write_text(
                (result.stdout or "") + "\n--- STDERR ---\n" + (result.stderr or ""),
                encoding="utf-8",
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"MAI STT thất bại ở cảnh {scene_id}. Xem {scene_out / 'stt.log'}.\n"
                    + (result.stderr or result.stdout)[-2500:]
                )

            words_file = scene_out / "mai_words.json"
            transcript_file = scene_out / "raw_transcript.txt"
            manifest_file = scene_out / "manifest.json"
            if not words_file.exists():
                raise RuntimeError(f"MAI không tạo mai_words.json cho cảnh {scene_id}.")
            words = json.loads(words_file.read_text(encoding="utf-8"))
            if not isinstance(words, list) or not any(w.get("start") is not None and w.get("end") is not None for w in words):
                raise RuntimeError(f"MAI không trả timestamp từng từ cho cảnh {scene_id}.")
            aligned[scene_id] = [
                {"w": w.get("w", ""), "start": w.get("start"), "end": w.get("end"), "score": w.get("score")}
                for w in words
            ]
            if transcript_file.exists():
                (transcript_dir / f"scene_{index:03d}_asr.txt").write_text(
                    transcript_file.read_text(encoding="utf-8"), encoding="utf-8"
                )
            if manifest_file.exists():
                (transcript_dir / f"scene_{index:03d}_stt_manifest.json").write_text(
                    manifest_file.read_text(encoding="utf-8"), encoding="utf-8"
                )
        return aligned

    def _run_forced_alignment(self, scenes, audio_items, transcript_dir, output_dir, repo):
        audio_dir = Path(audio_items[0]["mp3_path"]).parent
        command = [
            sys.executable, "-m", "realign.run_batch",
            "--txt-dir", str(transcript_dir.resolve()),
            "--audio-dir", str(audio_dir.resolve()),
            "--out-dir", str(output_dir.resolve()),
            "--device", settings.ALIGNMENT_DEVICE,
            "--window-sec", str(settings.ALIGNMENT_WINDOW_SEC),
        ]
        result = subprocess.run(
            command, cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        log_path = output_dir / "alignment.log"
        log_path.write_text((result.stdout or "") + "\n--- STDERR ---\n" + (result.stderr or ""), encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(
                "speech-to-subtitle realign thất bại. Kiểm tra alignment.log.\n" +
                (result.stderr or result.stdout)[-2500:]
            )

        manifest = output_dir / "manifest.csv"
        if manifest.exists():
            with manifest.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            failed = [row for row in rows if row.get("status") != "ok"]
            if failed:
                raise RuntimeError("Một số cảnh không căn chỉnh được: " + "; ".join(
                    f"{row.get('srt_name')}: {row.get('error')}" for row in failed
                ))

        aligned: dict[int, list[dict[str, Any]]] = {}
        for index, scene in enumerate(scenes, start=1):
            words_file = output_dir / "words" / f"scene_{index:03d}.json"
            if not words_file.exists():
                raise RuntimeError(f"Thiếu dữ liệu timestamp: {words_file.name}")
            payload = json.loads(words_file.read_text(encoding="utf-8"))
            words = payload.get("words", [])
            if not any(word.get("start") is not None and word.get("end") is not None for word in words):
                raise RuntimeError(f"Không căn chỉnh được từ nào trong {words_file.name}")
            aligned[int(scene["id"])] = words
        return aligned

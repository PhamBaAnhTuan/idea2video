import json
import logging
import traceback
from pathlib import Path
from typing import Any

from ..config import settings
from ..storage import project_dir, read_project, update_project
from .alignment_service import SpeechToSubtitleAlignmentService
from .gemini_service import GeminiScriptService
from .render_service import RemotionRenderService
from .subtitle_service import build_timeline, save_timeline, write_srt
from .tts_service import VieNeuTTSService, prepare_uploaded_audio

logger = logging.getLogger(__name__)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_stage(project_id: str, step: str, stage: str, progress: int, **changes: Any) -> None:
    project = read_project(project_id)
    steps = dict(project.get("steps") or {})
    steps[step] = "running"
    update_project(
        project_id,
        status="running",
        stage=stage,
        progress=progress,
        current_step=step,
        steps=steps,
        **changes,
    )
    logger.info("Project %s: %s (%s%%)", project_id, stage, progress)


def _finish_step(project_id: str, step: str, status: str = "completed") -> None:
    project = read_project(project_id)
    steps = dict(project.get("steps") or {})
    steps[step] = status
    update_project(
        project_id,
        steps=steps,
        current_step=None,
    )
    if status == "skipped":
        logger.info("Project %s: Bỏ qua bước %s vì đã có dữ liệu đầu vào.", project_id, step)


def run_pipeline(project_id: str) -> None:
    project = read_project(project_id)
    request = project["request"]
    folder = project_dir(project_id)
    try:
        script = project.get("script")
        if request.get("script_source", "generate") == "provided":
            if not script:
                raise RuntimeError("Project chọn dùng kịch bản có sẵn nhưng thiếu dữ liệu script.")
            _finish_step(project_id, "script", "skipped")
        else:
            _set_stage(project_id, "script", "1/5 · Gemini đang viết kịch bản", 5)
            script = GeminiScriptService().generate(request)
            _finish_step(project_id, "script")
        _write_json(folder / "script.json", script)
        (folder / "script.md").write_text(
            "# " + script["video_title"] + "\n\n" + "\n\n".join(
                f"## {scene['scene_title']}\n\n{scene['narration']}" for scene in script["scenes"]
            ), encoding="utf-8"
        )
        update_project(project_id, script=script)

        if request.get("audio_source", "tts") == "upload":
            uploaded_audio = request.get("uploaded_audio") or []
            if len(uploaded_audio) != len(script["scenes"]):
                raise RuntimeError(
                    f"Kịch bản có {len(script['scenes'])} cảnh nhưng audio upload có {len(uploaded_audio)} file."
                )
            _set_stage(project_id, "alignment", "Đang chuẩn hóa audio upload", 30)
            audio_items = prepare_uploaded_audio(uploaded_audio, folder)
            _finish_step(project_id, "tts", "skipped")
        else:
            _set_stage(project_id, "tts", "2/5 · VieNeu-TTS đang tạo giọng đọc", 20)
            audio_items = VieNeuTTSService().generate(
                script["scenes"], folder / "audio", request.get("voice") or settings.VIENEU_VOICE
            )
            _finish_step(project_id, "tts")
        _set_stage(project_id, "alignment", "3/5 · Đang căn chỉnh audio với lời thoại", 45)

        aligned_words = SpeechToSubtitleAlignmentService().align_scenes(
            script["scenes"], audio_items, folder / "transcripts", folder / "alignment"
        )
        _finish_step(project_id, "alignment")
        _set_stage(project_id, "timeline", "4/5 · Đang tạo timeline phụ đề từng câu", 70)
        timeline = build_timeline(
            script, audio_items, aligned_words, settings.SCENE_GAP_SECONDS, request["aspect_ratio"]
        )
        timeline["project_name"] = project.get("name", "")
        timeline["template"] = request.get("video_template", "cinematic")
        # Replace a placeholder with the final static-file path used by Remotion.
        for scene in timeline["scenes"]:
            scene["audio_src"] = f"jobs/{project_id}/scene_{int(scene['id']):03d}.mp3"
        save_timeline(timeline, folder / "timeline.json")
        write_srt(timeline["sentences"], folder / "subtitles.srt")
        _write_json(folder / "words.json", {
            str(scene_id): words for scene_id, words in aligned_words.items()
        })
        _finish_step(project_id, "timeline")

        _set_stage(project_id, "render", "5/5 · Remotion đang dựng video", 82, timeline=timeline)
        video_path = folder / "video.mp4"
        RemotionRenderService().render(
            project_id, timeline, audio_items, folder / "renderer" / "input-props.json", video_path
        )
        artifacts = {
            "video": f"/files/{project_id}/video.mp4",
            "script_json": f"/files/{project_id}/script.json",
            "script_markdown": f"/files/{project_id}/script.md",
            "timeline_json": f"/files/{project_id}/timeline.json",
            "subtitles_srt": f"/files/{project_id}/subtitles.srt",
            "words_json": f"/files/{project_id}/words.json",
        }
        update_project(project_id, status="completed", stage="Hoàn tất", progress=100, artifacts=artifacts)
        _finish_step(project_id, "render")
        logger.info("Project %s: Hoàn tất (100%%)", project_id)
    except Exception as exc:  # persist actionable error for the UI
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("Project %s pipeline failed: %s", project_id, error)
        (folder / "pipeline-error.txt").write_text(error + "\n\n" + traceback.format_exc(), encoding="utf-8")
        failed_project = read_project(project_id)
        steps = dict(failed_project.get("steps") or {})
        current_step = failed_project.get("current_step")
        if current_step in steps:
            steps[current_step] = "failed"
        update_project(
            project_id,
            status="failed",
            stage="Pipeline thất bại",
            error=error,
            progress=100,
            current_step=None,
            steps=steps,
        )

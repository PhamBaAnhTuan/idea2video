import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..config import settings


class RemotionRenderService:
    def render(self, project_id: str, timeline: dict[str, Any], audio_items: list[dict[str, Any]],
               props_path: Path, output_path: Path) -> None:
        renderer = settings.RENDERER_DIR
        if not (renderer / "render.mjs").exists():
            raise RuntimeError(f"Không tìm thấy Remotion renderer: {renderer}")
        public_job_dir = renderer / "public" / "jobs" / project_id
        public_job_dir.mkdir(parents=True, exist_ok=True)

        audio_tracks = []
        for item in audio_items:
            source = Path(item["mp3_path"])
            destination_name = source.name
            shutil.copy2(source, public_job_dir / destination_name)
            scene_start = next(
                float(scene["start"]) for scene in timeline["scenes"]
                if int(scene["id"]) == int(item["scene_id"])
            )
            audio_tracks.append({
                "src": f"jobs/{project_id}/{destination_name}",
                "start": scene_start,
                "duration": float(item["duration_seconds"]),
            })

        props = {
            "title": timeline["video_title"],
            "projectName": timeline.get("project_name") or timeline["video_title"],
            "template": timeline.get("template", "cinematic"),
            "aspectRatio": timeline["aspect_ratio"],
            "durationSeconds": timeline["duration_seconds"],
            "scenes": timeline["scenes"],
            "sentences": timeline["sentences"],
            "audioTracks": audio_tracks,
        }
        props_path.parent.mkdir(parents=True, exist_ok=True)
        props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [settings.NODE_BIN, "render.mjs", str(props_path.resolve()), str(output_path.resolve())],
            cwd=str(renderer), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        (output_path.parent / "render.log").write_text(
            (result.stdout or "") + "\n--- STDERR ---\n" + (result.stderr or ""), encoding="utf-8"
        )
        if result.returncode != 0 or not output_path.exists():
            raise RuntimeError("Remotion render thất bại. Xem render.log.\n" + (result.stderr or result.stdout)[-3000:])

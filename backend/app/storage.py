import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import settings

_LOCK = threading.RLock()
logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_dir(project_id: str) -> Path:
    # UUID validation prevents path traversal through project_id.
    try:
        from uuid import UUID
        UUID(project_id)
    except ValueError as exc:
        raise ValueError("Invalid project id") from exc
    return settings.DATA_DIR / project_id


def read_project(project_id: str) -> dict[str, Any]:
    path = project_dir(project_id) / "project.json"
    if not path.exists():
        raise FileNotFoundError(project_id)
    with _LOCK:
        return json.loads(path.read_text(encoding="utf-8"))


def write_project(project_id: str, data: dict[str, Any]) -> None:
    folder = project_dir(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = utc_now()
    tmp = folder / "project.json.tmp"
    with _LOCK:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(folder / "project.json")


def update_project(project_id: str, **changes: Any) -> dict[str, Any]:
    with _LOCK:
        data = read_project(project_id)
        data.update(changes)
        write_project(project_id, data)
        return data


def create_project(request_data: dict[str, Any], script: dict[str, Any] | None = None) -> dict[str, Any]:
    project_id = str(uuid4())
    folder = project_dir(project_id)
    project_name = " ".join(str(request_data.get("project_name") or "").split())
    project_name = (
        project_name
        or " ".join(str((script or {}).get("video_title") or "").split())
        or " ".join(str(request_data.get("idea") or "").split())
        or "Dự án mới"
    )
    if len(project_name) > 100:
        project_name = project_name[:100].rsplit(" ", 1)[0] or project_name[:100]
    for child in ("audio", "transcripts", "alignment", "renderer"):
        (folder / child).mkdir(parents=True, exist_ok=True)
    data = {
        "id": project_id,
        "name": project_name,
        "video_template": request_data.get("video_template", "cinematic"),
        "status": "queued",
        "stage": "Đang chờ xử lý",
        "progress": 0,
        "current_step": None,
        "steps": {
            "script": "pending",
            "tts": "pending",
            "alignment": "pending",
            "timeline": "pending",
            "render": "pending",
        },
        "error": None,
        "request": request_data,
        "script": script,
        "timeline": None,
        "artifacts": {},
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    write_project(project_id, data)
    return data


def list_projects(limit: int = 100) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("limit must be positive")
    projects: list[dict[str, Any]] = []
    if not settings.DATA_DIR.exists():
        return projects

    for project_file in settings.DATA_DIR.glob("*/project.json"):
        project_id = project_file.parent.name
        try:
            project = read_project(project_id)
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping unreadable project %s: %s", project_id, exc)
            continue
        projects.append({
            "id": project_id,
            "name": (
                project.get("name")
                or (project.get("script") or {}).get("video_title")
                or (project.get("request") or {}).get("idea")
                or "Dự án"
            ),
            "status": project.get("status", "failed"),
            "stage": project.get("stage", ""),
            "progress": project.get("progress", 0),
            "created_at": project.get("created_at", ""),
            "updated_at": project.get("updated_at", ""),
            "video_template": project.get(
                "video_template", (project.get("request") or {}).get("video_template", "cinematic")
            ),
        })
    projects.sort(key=lambda project: project["created_at"], reverse=True)
    return projects[:limit]


def fail_interrupted_projects() -> None:
    if not settings.DATA_DIR.exists():
        return

    for project_file in settings.DATA_DIR.glob("*/project.json"):
        project_id = project_file.parent.name
        try:
            project = read_project(project_id)
        except ValueError:
            logger.warning("Skipping project with invalid ID: %s", project_id)
            continue

        if project["status"] not in {"queued", "running"}:
            continue

        error = "Pipeline bị gián đoạn do backend khởi động lại. Vui lòng tạo project mới."
        update_project(
            project_id,
            status="failed",
            stage="Pipeline bị gián đoạn",
            error=error,
            progress=100,
        )
        logger.warning("Project %s marked failed because its pipeline was interrupted.", project_id)

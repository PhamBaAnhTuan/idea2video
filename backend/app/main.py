import importlib.util
import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .config import settings
from .schemas import CreateProjectRequest
from .script_input import parse_provided_script
from .storage import create_project, fail_interrupted_projects, list_projects, read_project, update_project
from .services.pipeline import run_pipeline


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    fail_interrupted_projects()
    yield


app = FastAPI(title="Idea-to-Video API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.WEB_ORIGIN, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(settings.DATA_DIR)), name="files")
MAX_AUDIO_FILE_BYTES = 100 * 1024 * 1024
MAX_AUDIO_UPLOAD_BYTES = 300 * 1024 * 1024
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


def _parse_script(payload: CreateProjectRequest) -> dict[str, Any] | None:
    if payload.script_source == "generate":
        return None
    try:
        return parse_provided_script(payload.script_content or "", payload.script_format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _create_project_job(
    payload: CreateProjectRequest,
    background_tasks: BackgroundTasks,
    audio_files: list[UploadFile] | None = None,
) -> dict[str, Any]:
    script = _parse_script(payload)
    files = audio_files or []
    if payload.audio_source == "upload":
        if not files:
            raise HTTPException(status_code=422, detail="Hãy tải lên audio cho từng cảnh.")
        if script is not None and len(files) != len(script["scenes"]):
            raise HTTPException(
                status_code=422,
                detail=f"Kịch bản có {len(script['scenes'])} cảnh nhưng nhận được {len(files)} file audio.",
            )
        if len(files) > 50:
            raise HTTPException(status_code=422, detail="Mỗi project hỗ trợ tối đa 50 file audio.")
        total_size = 0
        for upload in files:
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
                raise HTTPException(
                    status_code=422,
                    detail=f"Định dạng audio không hỗ trợ: {suffix or '(không có phần mở rộng)'}.",
                )
            size = upload.size
            if size is None:
                upload.file.seek(0, 2)
                size = upload.file.tell()
                upload.file.seek(0)
            if size <= 0 or size > MAX_AUDIO_FILE_BYTES:
                raise HTTPException(status_code=422, detail="Mỗi file audio phải nhỏ hơn 100 MB và không rỗng.")
            total_size += size
        if total_size > MAX_AUDIO_UPLOAD_BYTES:
            raise HTTPException(status_code=422, detail="Tổng dung lượng audio không được vượt quá 300 MB.")
    elif files:
        raise HTTPException(status_code=422, detail="Đã gửi audio nhưng nguồn audio đang chọn là VieNeu TTS.")

    request_data = payload.model_dump(exclude={"script_content"})
    if script is not None and not request_data["idea"]:
        request_data["idea"] = script["video_title"]
    if payload.audio_source == "upload" and script is None:
        request_data["scene_count"] = len(files)
    project = create_project(request_data, script=script)

    if files:
        project_folder = settings.DATA_DIR / project["id"]
        upload_dir = project_folder / "audio" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        uploaded_audio = []
        for index, upload in enumerate(files, start=1):
            suffix = Path(upload.filename or "").suffix.lower()
            relative_path = Path("audio") / "uploads" / f"scene_{index:03d}{suffix}"
            destination = project_folder / relative_path
            await upload.seek(0)
            with destination.open("wb") as target:
                shutil.copyfileobj(upload.file, target)
            uploaded_audio.append({
                "scene_id": index,
                "path": relative_path.as_posix(),
                "filename": Path(upload.filename or f"scene_{index:03d}{suffix}").name,
            })
        request_data["uploaded_audio"] = uploaded_audio
        update_project(project["id"], request=request_data)

    background_tasks.add_task(run_pipeline, project["id"])
    return {
        "id": project["id"],
        "name": project["name"],
        "video_template": request_data.get("video_template", "cinematic"),
        "status": project["status"],
        "stage": project["stage"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "idea-to-video-api"}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    backend = settings.STT_BACKEND.strip().lower()
    if backend == "mai":
        stt_runtime_found = (
            settings.ALIGNMENT_REPO_DIR / "transcribe" / "mai_transcribe" / "run_pipeline.py"
        ).exists()
        stt_configured = bool(settings.OPENROUTER_API_KEY)
    elif backend == "forced_alignment":
        stt_runtime_found = (settings.ALIGNMENT_REPO_DIR / "realign" / "run_batch.py").exists()
        stt_configured = stt_runtime_found
    elif backend == "whisper":
        stt_runtime_found = importlib.util.find_spec("faster_whisper") is not None
        stt_configured = stt_runtime_found
    else:
        stt_runtime_found = False
        stt_configured = False
    return {
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "stt_configured": stt_configured,
        "stt_backend": backend,
        "alignment_repo_found": stt_runtime_found,
        "stt_runtime_found": stt_runtime_found,
        "renderer_found": (settings.RENDERER_DIR / "render.mjs").exists(),
        "voices": ["Hải Đăng", "Mai Anh", "Thùy Dung", "Quang Sơn", "Ngọc Huyền", "Trúc Ly", "Phạm Tuyên"],
    }


@app.post("/api/projects", status_code=202)
async def create_video_project(payload: CreateProjectRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    if payload.audio_source == "upload":
        raise HTTPException(status_code=422, detail="Dùng /api/projects/import để tải audio lên.")
    return await _create_project_job(payload, background_tasks)


@app.post("/api/projects/import", status_code=202)
async def create_video_project_from_files(
    background_tasks: BackgroundTasks,
    request_data: str = Form(...),
    audio_files: list[UploadFile] | None = File(default=None),
) -> dict[str, Any]:
    try:
        payload = CreateProjectRequest.model_validate_json(request_data)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        detail = exc.errors() if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(status_code=422, detail=detail) from exc
    return await _create_project_job(payload, background_tasks, audio_files)


@app.get("/api/projects")
def get_projects(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return {"projects": list_projects(limit)}


@app.get("/api/projects/{project_id}")
def get_video_project(project_id: str) -> dict[str, Any]:
    try:
        project = read_project(project_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    return project

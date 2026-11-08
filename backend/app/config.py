from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_TIMEOUT_SECONDS: int = 120
    VIENEU_VOICE: str = "Hải Đăng"
    VIENEU_BACKEND: str = "onnx"
    ALIGNMENT_REPO_DIR: Path = PROJECT_ROOT / "vendor" / "speech-to-subtitle"
    STT_BACKEND: str = "whisper"  # whisper = local ASR; mai = hosted ASR; forced_alignment = align script locally
    OPENROUTER_API_KEY: str = ""
    MAI_MODEL: str = "microsoft/mai-transcribe-2"
    MAI_LANGUAGE: str = "vi"
    MAI_WORKERS: int = 2
    WHISPER_MODEL: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_LANGUAGE: str = "vi"
    ALIGNMENT_DEVICE: str = "cpu"
    ALIGNMENT_WINDOW_SEC: int = 1500
    FFMPEG_BIN: str = "ffmpeg"
    FFPROBE_BIN: str = "ffprobe"
    NODE_BIN: str = "node"
    DATA_DIR: Path = PROJECT_ROOT / "data"
    RENDERER_DIR: Path = PROJECT_ROOT / "apps" / "renderer"
    WEB_ORIGIN: str = "http://127.0.0.1:5173"
    SCENE_GAP_SECONDS: float = 0.18


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

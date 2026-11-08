from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class CreateProjectRequest(BaseModel):
    project_name: str = Field(default="", max_length=100)
    idea: str = Field(default="", max_length=3000)
    audience: str = Field(default="Người xem phổ thông", max_length=300)
    tone: str = Field(default="Dễ hiểu, gần gũi, có nhịp kể chuyện", max_length=300)
    duration_minutes: int = Field(default=1, ge=1, le=10)
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    voice: str = Field(default="Hải Đăng", max_length=100)
    script_source: Literal["generate", "provided"] = "generate"
    script_format: Literal["text", "json"] = "text"
    script_content: str | None = Field(default=None, max_length=500_000)
    audio_source: Literal["tts", "upload"] = "tts"
    video_template: Literal["cinematic", "captions", "bullet_list", "table", "chart"] = "cinematic"

    @field_validator("project_name")
    @classmethod
    def strip_project_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("idea")
    @classmethod
    def strip_idea(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_sources(self) -> "CreateProjectRequest":
        if self.script_source == "generate" and len(self.idea) < 10:
            raise ValueError("Ý tưởng cần ít nhất 10 ký tự khi chọn Gemini tạo kịch bản.")
        if self.script_source == "provided" and not (self.script_content or "").strip():
            raise ValueError("Hãy nhập nội dung hoặc chọn file kịch bản có sẵn.")
        return self

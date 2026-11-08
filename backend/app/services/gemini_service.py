import json
import logging
import re
import time
from typing import Any

from google import genai
from google.genai import types

from ..config import settings

logger = logging.getLogger(__name__)


SYSTEM_INSTRUCTION = """Bạn là biên kịch video tiếng Việt chuyên nghiệp. Viết lời dẫn tự nhiên, dễ đọc thành tiếng.
Không bịa số liệu, nghiên cứu, tên tổ chức hoặc trích dẫn. Nếu ý tưởng chứa dữ kiện cần xác minh,
hãy diễn đạt thận trọng, không tự tạo con số. Nội dung narration phải là lời có thể đọc trực tiếp;
không chèn chỉ dẫn máy quay vào narration. Trả về JSON hợp lệ, không Markdown."""


class GeminiScriptService:
    def __init__(self) -> None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("Thiếu GEMINI_API_KEY trong backend/.env")
        if settings.GEMINI_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("GEMINI_TIMEOUT_SECONDS phải lớn hơn 0.")
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=settings.GEMINI_TIMEOUT_SECONDS * 1000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
Tạo kịch bản video tiếng Việt dựa trên ý tưởng sau.
Ý tưởng: {request['idea']}
Đối tượng xem: {request['audience']}
Phong cách: {request['tone']}
Thời lượng mục tiêu: khoảng {request['duration_minutes']} phút.

Yêu cầu:
- {f"Tạo chính xác {request['scene_count']} cảnh để khớp với số file audio có sẵn." if request.get('scene_count') else "Tạo 4 đến 8 cảnh, có mở đầu thu hút, phần triển khai và kết thúc."}
- Tổng lời thoại phù hợp thời lượng; tốc độ đọc tiếng Việt khoảng 125-145 từ/phút.
- Mỗi narration là 1-3 câu hoàn chỉnh, có dấu câu rõ ràng để căn chỉnh timeline.
- Không ghi nhãn "Người dẫn:" hoặc chú thích ngoài lời thoại.
- visual_prompt mô tả một hình ảnh/khung cảnh minh họa ngắn gọn, không đưa chữ cần render vào hình.
- key_points có 1-3 ý ngắn để hiển thị trong cảnh.
- Không tạo timestamp; timestamp sẽ được căn chỉnh trực tiếp từ audio.

Trả về đúng cấu trúc JSON:
{{
  "video_title": "Tiêu đề video ngắn gọn",
  "hook": "Câu mở đầu thu hút",
  "scenes": [
    {{
      "id": 1,
      "scene_title": "Tiêu đề cảnh",
      "narration": "Lời thoại tiếng Việt có dấu câu.",
      "visual_prompt": "Mô tả hình ảnh minh họa.",
      "key_points": ["Ý chính 1", "Ý chính 2"]
    }}
  ]
}}
"""
        logger.info(
            "Gửi yêu cầu tạo kịch bản tới Gemini (model=%s, timeout=%ss).",
            settings.GEMINI_MODEL,
            settings.GEMINI_TIMEOUT_SECONDS,
        )
        started_at = time.monotonic()
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0.7,
                    automatic_continuation=False,
                ),
            )
        except Exception:
            elapsed = time.monotonic() - started_at
            logger.exception("Gemini request thất bại sau %.1f giây.", elapsed)
            raise
        finally:
            self.client.close()

        logger.info("Gemini trả lời sau %.1f giây.", time.monotonic() - started_at)
        raw = (response.text or "").strip()
        candidates = response.candidates or []
        finish_reason = candidates[0].finish_reason if candidates else "no_candidate"
        if not raw:
            feedback = response.prompt_feedback
            block_reason = feedback.block_reason if feedback else None
            raise RuntimeError(
                "Gemini không trả về nội dung kịch bản "
                f"(finish_reason={finish_reason}, block_reason={block_reason})."
            )
        try:
            script = json.loads(raw)
        except json.JSONDecodeError:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
            try:
                script = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Gemini trả về JSON không hợp lệ "
                    f"(finish_reason={finish_reason}): {exc}"
                ) from exc

        if not isinstance(script, dict):
            raise RuntimeError("Gemini trả về JSON nhưng nội dung gốc không phải object.")

        scenes = script.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            raise RuntimeError("Kịch bản Gemini không có danh sách scenes hợp lệ.")
        normalized = []
        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue
            narration = str(scene.get("narration", "")).strip()
            if not narration:
                continue
            key_points = scene.get("key_points")
            if not isinstance(key_points, list):
                key_points = []
            normalized.append({
                "id": index,
                "scene_title": str(scene.get("scene_title") or f"Cảnh {index}"),
                "narration": narration,
                "visual_prompt": str(scene.get("visual_prompt") or "Minh họa tối giản, hiện đại"),
                "key_points": [str(x) for x in key_points[:3]],
            })
        if not normalized:
            raise RuntimeError("Kịch bản không có lời thoại để đọc.")
        expected_scene_count = request.get("scene_count")
        if expected_scene_count is not None and len(normalized) != expected_scene_count:
            raise RuntimeError(
                f"Gemini tạo {len(normalized)} cảnh nhưng cần đúng {expected_scene_count} cảnh "
                "để khớp với audio đã upload."
            )
        logger.info("Đã phân tích kịch bản Gemini thành công (%s cảnh).", len(normalized))
        return {
            "video_title": str(script.get("video_title") or "Video mới"),
            "hook": str(script.get("hook") or ""),
            "scenes": normalized,
        }

import json
import re
from typing import Any


def parse_provided_script(content: str, script_format: str) -> dict[str, Any]:
    if script_format == "json":
        try:
            script = json.loads(content.lstrip("\ufeff"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"File JSON không hợp lệ: {exc.msg} (dòng {exc.lineno}).") from exc
        if not isinstance(script, dict):
            raise ValueError("Script JSON phải là một object.")
        raw_scenes = script.get("scenes")
        if not isinstance(raw_scenes, list) or not raw_scenes:
            raise ValueError("Script JSON cần có danh sách scenes không rỗng.")
        if len(raw_scenes) > 50:
            raise ValueError("Mỗi kịch bản hỗ trợ tối đa 50 cảnh.")
        scenes = []
        for index, scene in enumerate(raw_scenes, start=1):
            if not isinstance(scene, dict):
                raise ValueError(f"Cảnh {index} trong script JSON phải là object.")
            narration = str(scene.get("narration") or "").strip()
            if not narration:
                raise ValueError(f"Cảnh {index} trong script JSON thiếu narration.")
            key_points = scene.get("key_points")
            if not isinstance(key_points, list):
                key_points = []
            scenes.append({
                "id": index,
                "scene_title": str(scene.get("scene_title") or f"Cảnh {index}"),
                "narration": narration,
                "visual_prompt": str(scene.get("visual_prompt") or "Minh họa tối giản, hiện đại"),
                "key_points": [str(item) for item in key_points[:3]],
            })
        return {
            "video_title": str(script.get("video_title") or "Video từ kịch bản có sẵn"),
            "hook": str(script.get("hook") or ""),
            "scenes": scenes,
        }

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs:
        raise ValueError("Không tìm thấy đoạn lời thoại trong file text.")
    if len(paragraphs) > 50:
        raise ValueError("Mỗi kịch bản hỗ trợ tối đa 50 đoạn/cảnh.")
    scenes = [
        {
            "id": index,
            "scene_title": f"Cảnh {index}",
            "narration": paragraph,
            "visual_prompt": "Minh họa tối giản, hiện đại",
            "key_points": [],
        }
        for index, paragraph in enumerate(paragraphs, start=1)
    ]
    return {
        "video_title": "Video từ kịch bản có sẵn",
        "hook": "",
        "scenes": scenes,
    }

import json
import re
from pathlib import Path
from typing import Any


def _join_words(words: list[dict[str, Any]]) -> str:
    text = " ".join(str(item.get("w", "")).strip() for item in words if str(item.get("w", "")).strip())
    # Remove spaces before Vietnamese/Latin punctuation and normalize quote spacing.
    text = re.sub(r"\s+([,.;:!?…%)\]])", r"\1", text)
    text = re.sub(r"([([{])\s+", r"\1", text)
    return text.strip()


def words_to_sentences(words: list[dict[str, Any]], scene_id: int, offset: float) -> list[dict[str, Any]]:
    valid = [w for w in words if w.get("start") is not None and w.get("end") is not None and w.get("w")]
    result: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        text = _join_words(current)
        if text:
            result.append({
                "scene_id": scene_id,
                "start": round(offset + float(current[0]["start"]), 3),
                "end": round(offset + float(current[-1]["end"]), 3),
                "text": text,
            })
        current = []

    for word in valid:
        if current and float(word["start"]) - float(current[-1]["end"]) >= 1.15:
            flush()
        current.append(word)
        token = str(word.get("w", "")).rstrip('"\'”’)]}')
        if re.search(r"[.!?…]$", token):
            flush()
    flush()
    return result


def to_srt_timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_timeline(script: dict[str, Any], scenes_audio: list[dict[str, Any]],
                   aligned_words: dict[int, list[dict[str, Any]]], gap_seconds: float,
                   aspect_ratio: str) -> dict[str, Any]:
    audio_by_id = {int(item["scene_id"]): item for item in scenes_audio}
    scene_offset = 0.0
    scenes_out: list[dict[str, Any]] = []
    sentences_out: list[dict[str, Any]] = []
    sentence_id = 1

    for scene in script["scenes"]:
        scene_id = int(scene["id"])
        audio = audio_by_id[scene_id]
        duration = float(audio["duration_seconds"])
        sentences = words_to_sentences(aligned_words[scene_id], scene_id, scene_offset)
        for sentence in sentences:
            sentence["id"] = sentence_id
            sentence_id += 1
            sentences_out.append(sentence)
        scenes_out.append({
            "id": scene_id,
            "scene_title": scene["scene_title"],
            "narration": scene["narration"],
            "visual_prompt": scene["visual_prompt"],
            "key_points": scene["key_points"],
            "start": round(scene_offset, 3),
            "end": round(scene_offset + duration, 3),
            "duration": round(duration, 3),
            "audio_src": f"jobs/PLACEHOLDER/scene_{scene_id:03d}.mp3",
        })
        scene_offset += duration + gap_seconds

    # Remove the artificial final gap from total duration.
    duration_seconds = max(0.0, scene_offset - gap_seconds) if scenes_out else 0.0
    return {
        "video_title": script["video_title"],
        "hook": script.get("hook", ""),
        "aspect_ratio": aspect_ratio,
        "fps": 30,
        "duration_seconds": round(duration_seconds, 3),
        "scenes": scenes_out,
        "sentences": sentences_out,
    }


def write_srt(sentences: list[dict[str, Any]], destination: Path) -> None:
    blocks = []
    for index, item in enumerate(sentences, start=1):
        start = float(item["start"])
        end = max(float(item["end"]), start + 0.35)
        blocks.append(
            f"{index}\n{to_srt_timestamp(start)} --> {to_srt_timestamp(end)}\n{item['text']}"
        )
    destination.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8-sig")


def save_timeline(timeline: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")

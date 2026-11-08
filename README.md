# Idea-to-Video Studio

Ứng dụng local chuyển **ý tưởng → kịch bản Gemini → giọng đọc VieNeu-TTS → căn chỉnh audio → phụ đề/timeline từng câu → video Remotion**.

> Bản triển khai đầu tiên tập trung vào pipeline chạy được local, lời thoại tiếng Việt và timestamp lấy từ audio thật. Video mẫu hiện dùng motion-graphics/template theo từng cảnh (tiêu đề, key points, nền chuyển động và phụ đề). `visual_prompt` được lưu trong script/timeline để bổ sung bước sinh ảnh hoặc gắn media ở phiên bản tiếp theo; phiên bản này chưa gọi dịch vụ sinh ảnh.

## 1. Cấu trúc

```text
idea2video/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                  # FastAPI
│  │  ├─ config.py                # Cấu hình qua .env
│  │  ├─ script_input.py          # Chuẩn hóa script TXT/JSON có sẵn
│  │  ├─ storage.py               # Lưu project/job
│  │  └─ services/
│  │     ├─ gemini_service.py     # Gemini generate_content → JSON script
│  │     ├─ tts_service.py        # VieNeu-TTS → WAV/MP3
│  │     ├─ alignment_service.py  # speech-to-subtitle MAI STT / MMS adapter
│  │     ├─ subtitle_service.py   # Word timings → câu/SRT/JSON
│  │     ├─ render_service.py     # Gọi Remotion renderer
│  │     └─ pipeline.py           # Điều phối 5 bước
│  ├─ requirements.txt
│  ├─ requirements-stt.txt
│  └─ .env.example
├─ apps/
│  ├─ web/                        # React + Vite UI
│  └─ renderer/                   # Remotion composition + render API
├─ vendor/speech-to-subtitle/     # Clone tự động từ GitHub khi setup
├─ data/                          # Kịch bản, audio, alignment, video
├─ setup.ps1
└─ start.ps1
```

## 2. Thành phần mã nguồn

- **Gemini:** dùng Google GenAI Python SDK (`google-genai`) gọi trực tiếp `models.generate_content` cho một prompt, yêu cầu JSON và tắt tự động continuation để tránh request ngầm kéo dài. Model có thể thay trong `backend/.env` qua `GEMINI_MODEL`.
- **VieNeu-TTS:** dùng Python SDK `vieneu`, mặc định v3 Turbo; mỗi cảnh được tạo thành một audio riêng. SDK mặc định chạy ONNX/CPU khi cấu hình `VIENEU_BACKEND=onnx`.
- **STT/timeline:** mặc định dùng `faster-whisper` chạy Whisper cục bộ, nhận diện audio tiếng Việt và lấy timestamp từng từ mà không gọi dịch vụ STT trả phí. Model tải về ở lần chạy đầu; CPU dùng `small`/`int8` mặc định, không cần NVIDIA GPU. Có thể đổi sang `STT_BACKEND=mai` để dùng MAI qua OpenRouter (có phí theo chính sách dịch vụ), hoặc `STT_BACKEND=forced_alignment` để căn kịch bản có sẵn vào audio bằng MMS cục bộ. Forced alignment không nhận diện lời thoại và cần kịch bản khớp với audio.
- **Remotion:** có composition cho video dọc/ngang/vuông và các bố cục tự triển khai: điện ảnh, chữ nổi bật, gạch đầu dòng, bảng tóm tắt và biểu đồ thời lượng cảnh. Các ý tưởng bố cục được tham khảo từ nhóm template phổ biến của [Locomotion Templates](https://github.com/Thedurancode/locomotion-templates); không sao chép mã template của repo đó. Python copy audio vào thư mục `public/jobs` để Remotion đóng gói media khi render.

## 3. Yêu cầu máy tính

- Windows 10/11 64-bit.
- Python **3.12** (64-bit) và Python Launcher `py`.
- Node.js 20+ và npm.
- Git.
- FFmpeg + FFprobe có trong PATH.
- RAM 16 GB được khuyến nghị nếu xử lý audio dài; mô hình TTS và VAD cần tài nguyên bộ nhớ.
- Internet ở lần chạy đầu để tải model Whisper cục bộ. OpenRouter API key chỉ cần nếu chọn `STT_BACKEND=mai`.

**GPU:** VieNeu và Whisper mặc định chạy CPU. Whisper có thể dùng NVIDIA GPU sau khi cài CTranslate2/CUDA tương thích. `forced_alignment` cần PyTorch/Torchaudio tương thích; repo upstream khuyến nghị NVIDIA CUDA. Không bật `cuda` chỉ vì máy có GPU AMD.

## 4. Cài đặt trên Windows

Mở PowerShell tại thư mục `idea2video`:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

Script sẽ:
1. Kiểm tra Python 3.12, Node, Git, FFmpeg.
2. Clone `https://github.com/vuhai2002/speech-to-subtitle` vào `vendor/speech-to-subtitle`.
3. Tạo `backend/.venv`, cài dependencies backend và stack CPU cho Whisper/MAI VAD.
4. Cài npm dependencies cho Remotion và Web UI.
5. Tạo `backend/.env` từ `.env.example` nếu chưa có.

Mở `backend/.env`. Gemini API key chỉ cần nếu tạo kịch bản bằng Gemini; Whisper mặc định chạy cục bộ, không cần OpenRouter:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash
GEMINI_TIMEOUT_SECONDS=120
VIENEU_VOICE=Hải Đăng
VIENEU_BACKEND=onnx
ALIGNMENT_REPO_DIR=../vendor/speech-to-subtitle
# Local Whisper; no paid STT API
STT_BACKEND=whisper
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_LANGUAGE=vi
# Optional: only if using STT_BACKEND=mai
OPENROUTER_API_KEY=your_openrouter_api_key
MAI_MODEL=microsoft/mai-transcribe-2
MAI_LANGUAGE=vi
MAI_WORKERS=2
# Optional: forced_alignment device; requires compatible PyTorch/Torchaudio
ALIGNMENT_DEVICE=cpu
ALIGNMENT_WINDOW_SEC=1500
```

Nếu model Gemini của tài khoản chưa hỗ trợ tên model mặc định, đổi `GEMINI_MODEL` thành model Gemini Flash đang được bật trong Google AI Studio.
Gemini request timeout mặc định sau 120 giây; có thể chỉnh bằng `GEMINI_TIMEOUT_SECONDS`. Nếu request lỗi hoặc quá thời gian, project chuyển sang `failed` và lỗi được ghi vào terminal cùng `pipeline-error.txt`. Các project còn `queued`/`running` sau khi backend khởi động lại cũng được đánh dấu là bị gián đoạn thay vì hiển thị đang chạy mãi.

Chạy ứng dụng:

```powershell
.\start.ps1
```

- Backend và Web UI chạy cùng trong terminal hiện tại; log được gắn nhãn `[backend]` và `[web]`, lỗi hiển thị màu đỏ.
- Log backend hiển thị từng bước pipeline và traceback khi xử lý project thất bại.
- Nhấn `Ctrl+C` trong terminal để dừng cả hai dịch vụ.
- Web UI: http://127.0.0.1:5173
- Backend API: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

## 5. Cách chạy pipeline

1. Chọn nguồn kịch bản: Gemini tạo mới, hoặc dùng file `.txt`/`.json` và nội dung dán vào giao diện. Với `.txt`, mỗi đoạn cách nhau bằng một dòng trống sẽ thành một cảnh.
2. Chọn nguồn âm thanh: VieNeu tạo audio theo từng cảnh, hoặc tải lên một file WAV/MP3/M4A/AAC/FLAC/OGG cho mỗi cảnh theo đúng thứ tự.
3. Các bước viết script và TTS tự bỏ qua nếu đã cung cấp dữ liệu tương ứng. Nếu chọn Gemini cùng audio upload, Gemini được yêu cầu tạo đúng số cảnh bằng số file audio.
4. Whisper (mặc định) hoặc MAI nhận diện audio và tạo timestamp; hoặc cấu hình `STT_BACKEND=forced_alignment` để căn script với audio.
5. Đặt tên dự án để tra cứu/sắp xếp sau này, chọn một template hình ảnh, rồi Remotion dựng video theo bố cục đó.

Audio được chuẩn hóa bằng FFmpeg trước khi căn chỉnh. Mỗi file upload tối đa 100 MB, tổng dung lượng tối đa 300 MB và tối đa 50 cảnh. Bảng tiến trình hiển thị rõ bước hoàn thành, đang chạy và được bỏ qua.

Tên dự án được lưu cùng dữ liệu và hiển thị trong danh sách dự án đã lưu; có thể sắp xếp theo thời gian tạo hoặc tên A–Z. Nếu để trống, tên được lấy tự động từ tiêu đề kịch bản, hoặc ý tưởng.

Các template hiện có:
- **Điện ảnh:** thẻ cảnh nền gradient, tiêu đề và ý chính.
- **Chữ nổi bật:** tiêu đề lớn và phụ đề kinetic.
- **Gạch đầu dòng:** làm nổi bật từng ý trong cảnh.
- **Bảng tóm tắt:** trình bày ý chính thành hàng.
- **Biểu đồ nhịp độ:** biểu đồ thời lượng audio thật của các cảnh; không tạo số liệu chủ đề giả.

## 6. API

- `GET /health` – health check.
- `GET /api/config` – kiểm tra Gemini, STT repo, renderer.
- `POST /api/projects` – tạo project và chạy pipeline nền.
- `POST /api/projects/import` – multipart form gồm `request_data` (JSON cấu hình) và tùy chọn `audio_files` để dùng script/audio có sẵn.
- `GET /api/projects/{id}` – đọc trạng thái, script, timeline và artifacts.
- `GET /files/{project_id}/...` – tải artifact.

Ví dụ tạo project:

```json
{
  "idea": "Giải thích trí tuệ nhân tạo đang thay đổi việc học như thế nào",
  "audience": "Sinh viên",
  "tone": "Gần gũi, dễ hiểu",
  "duration_minutes": 1,
  "aspect_ratio": "9:16",
  "voice": "Hải Đăng"
}
```

## 7. Đầu ra của một project

```text
data/<project-id>/
├─ script.json
├─ script.md
├─ audio/
│  ├─ scene_001.wav
│  ├─ scene_001.mp3
│  └─ ...
├─ transcripts/
│  ├─ scene_001.txt
│  └─ ...
├─ alignment/
│  └─ mai/scene_001/
│     ├─ mai_words.json
│     ├─ raw_transcript.txt
│     ├─ manifest.json
│     └─ stt.log
├─ words.json
├─ timeline.json
├─ subtitles.srt
├─ video.mp4
└─ renderer/input-props.json
```

`timeline.json` có hai lớp mốc:
- `scenes`: khoảng thời gian của từng cảnh.
- `sentences`: `start`, `end`, `text`, `scene_id` của từng câu thoại.

## 8. Kiểm tra lỗi thường gặp

- **Gemini 401/403:** kiểm tra `GEMINI_API_KEY`, quyền Gemini API và tên `GEMINI_MODEL`.
- **VieNeu import/model error:** kiểm tra `pip show vieneu`; lần đầu cần Internet để tải model. Có thể thử ứng dụng VieNeu riêng để xác nhận SDK hoạt động.
- **Không tìm thấy MP3:** kiểm tra FFmpeg/FFprobe trong PATH và `audio/scene_NNN.mp3`.
- **Không tìm thấy realign:** kiểm tra `ALIGNMENT_REPO_DIR`; repo phải có `realign/run_batch.py`.
- **Lỗi Whisper/STT:** kiểm tra `faster-whisper` trong `backend/.venv` và kết nối Internet ở lần chạy đầu để tải model; xem `alignment/whisper/scene_NNN/stt.log`.
- **MAI báo lỗi/quota:** xem `alignment/mai/scene_NNN/stt.log`, `manifest.json` và kiểm tra OpenRouter API key / số dư.
- **Lỗi forced alignment:** cài `vendor/speech-to-subtitle/requirements.txt` cùng bộ Torch/Torchaudio tương thích.
- **Render lỗi:** xem `render.log`, đảm bảo `npm install` trong `apps/renderer` đã hoàn tất và Node nằm trong PATH.

## 9. Giới hạn của bản đầu tiên

- Script chạy liền mạch qua từng cảnh; mỗi cảnh tạo một audio riêng để timeline khớp theo track.
- Mặc định timestamp được MAI STT nhận diện trực tiếp từ audio đã tổng hợp; transcript ASR có thể khác script Gemini ở một vài từ. file `scene_NNN.txt` (lời Gemini) và `scene_NNN_asr.txt` (STT) trong thư mục `transcripts` cho phép đối chiếu. Nếu cần ép timeline bám đúng từng chữ trong script, hãy cân nhắc MMS forced alignment với thiết bị NVIDIA CUDA phù hợp.
- Phân đoạn câu dựa vào dấu câu trong lời thoại và khoảng lặng giữa từ. Nếu script thiếu dấu câu, một đoạn dài có thể được gom thành câu dài; vì vậy cần giữ dấu câu trong narration.
- Video dùng template motion-graphics, chưa tự sinh ảnh/video minh họa từ `visual_prompt`. Có thể bổ sung image generation hoặc thư viện stock ở module tiếp theo.
- Đây là bản local single-user; chưa có đăng nhập, queue phân tán, retry dashboard, lưu trữ cloud hoặc giới hạn tài nguyên cho triển khai công khai.
- Kiểm tra điều khoản sử dụng của Google Gemini, VieNeu-TTS và Remotion trước khi thương mại hóa hoặc triển khai cho nhiều người dùng.

## 10. Tham khảo

- VieNeu-TTS (official): https://github.com/pnnbao97/VieNeu-TTS
- speech-to-subtitle: https://github.com/vuhai2002/speech-to-subtitle
- Remotion prompt-to-video template: https://github.com/remotion-dev/template-prompt-to-video
- Remotion TikTok captions template: https://github.com/remotion-dev/template-tiktok
- Remotion render server template: https://github.com/remotion-dev/template-render-server
- Gemini API: https://ai.google.dev/gemini-api/docs

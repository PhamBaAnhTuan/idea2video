$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host '== Idea-to-Video: setup ==' -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Chưa cài Git. Cài Git for Windows rồi chạy lại setup.ps1.' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Chưa cài Node.js 20+. Cài Node.js rồi chạy lại setup.ps1.' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
  throw 'Chưa tìm thấy FFmpeg/FFprobe trong PATH. Có thể cài bằng: winget install Gyan.FFmpeg'
}

if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) { throw 'Không tìm thấy curl.exe; cài curl hoặc cập nhật Windows trước khi chạy STT.' }

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PyLauncher) { throw 'Cần Python 3.12 và Python Launcher (py.exe).' }
& py -3.12 --version
if ($LASTEXITCODE -ne 0) { throw 'Không tìm thấy Python 3.12. Hãy cài Python 3.12 (64-bit), sau đó chạy lại.' }

$Vendor = Join-Path $Root 'vendor/speech-to-subtitle'
if (-not (Test-Path (Join-Path $Vendor 'transcribe/mai_transcribe/run_pipeline.py'))) {
  New-Item -ItemType Directory -Force -Path (Join-Path $Root 'vendor') | Out-Null
  git clone --depth 1 https://github.com/vuhai2002/speech-to-subtitle.git $Vendor
  if ($LASTEXITCODE -ne 0) { throw 'Không clone được speech-to-subtitle. Kiểm tra kết nối mạng/Git.' }
}

$Venv = Join-Path $Root 'backend/.venv'
if (-not (Test-Path $Venv)) { & py -3.12 -m venv $Venv; if ($LASTEXITCODE -ne 0) { throw 'Không tạo được Python virtual environment.' } }
$Python = Join-Path $Venv 'Scripts/python.exe'
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Không cập nhật được pip.' }
& $Python -m pip install -r (Join-Path $Root 'backend/requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Không cài được backend requirements.' }
# MAI STT uses CPU VAD and native word timestamps; no MMS/CUDA stack is needed.
& $Python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'Không cài được PyTorch CPU.' }
& $Python -m pip install -r (Join-Path $Root 'backend/requirements-stt.txt')
if ($LASTEXITCODE -ne 0) { throw 'Không cài được STT/VAD requirements.' }

if (-not (Test-Path (Join-Path $Root 'backend/.env'))) {
  Copy-Item (Join-Path $Root 'backend/.env.example') (Join-Path $Root 'backend/.env')
  Write-Host 'Đã tạo backend/.env; hãy điền GEMINI_API_KEY.' -ForegroundColor Yellow
}

Push-Location (Join-Path $Root 'apps/renderer')
npm install
if ($LASTEXITCODE -ne 0) { Pop-Location; throw 'Không cài được dependencies cho Remotion renderer.' }
Pop-Location
Push-Location (Join-Path $Root 'apps/web')
npm install
if ($LASTEXITCODE -ne 0) { Pop-Location; throw 'Không cài được dependencies cho Web UI.' }
Pop-Location

Write-Host ''
Write-Host 'Setup hoàn tất.' -ForegroundColor Green
Write-Host '1) Điền GEMINI_API_KEY trong backend/.env'
Write-Host '2) Chạy .\start.ps1'
Write-Host 'Lưu ý: lần chạy đầu VieNeu và VAD có thể tải model; MAI STT gọi OpenRouter và tính phí theo audio.' -ForegroundColor Yellow

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'backend'
$Web = Join-Path $Root 'apps/web'
$Python = Join-Path $Backend '.venv/Scripts/python.exe'
$NodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$Vite = Join-Path $Web 'node_modules/vite/bin/vite.js'

if (-not (Test-Path $Python)) { throw 'Chưa setup. Hãy chạy .\setup.ps1 trước.' }
if (-not (Test-Path (Join-Path $Backend '.env'))) { throw 'Thiếu backend/.env. Hãy copy từ backend/.env.example và điền GEMINI_API_KEY.' }
if (-not $NodeCommand) { throw 'Không tìm thấy Node.js trong PATH. Hãy cài Node.js 20+.' }
if (-not (Test-Path $Vite)) { throw 'Chưa cài dependencies cho Web UI. Hãy chạy .\setup.ps1 trước.' }

function Write-NewLogLines {
  param(
    [string]$Path,
    [string]$Service,
    [ConsoleColor]$Color,
    [hashtable]$State,
    [string]$StreamName,
    [switch]$Flush
  )

  if (-not (Test-Path $Path)) { return }

  $offset = [long]$State["${StreamName}Offset"]
  $pending = [string]$State["${StreamName}Pending"]
  $fileStream = [System.IO.File]::Open(
    $Path,
    [System.IO.FileMode]::Open,
    [System.IO.FileAccess]::Read,
    [System.IO.FileShare]::ReadWrite
  )
  try {
    if ($fileStream.Length -lt $offset) {
      $offset = 0
      $pending = ''
    }
    [void]$fileStream.Seek($offset, [System.IO.SeekOrigin]::Begin)
    $byteCount = [int][Math]::Min($fileStream.Length - $offset, 1048576)
    if ($byteCount -gt 0) {
      $buffer = New-Object byte[] $byteCount
      $read = $fileStream.Read($buffer, 0, $byteCount)
      $offset += $read
      $text = $pending + [System.Text.Encoding]::UTF8.GetString($buffer, 0, $read)
      $lines = $text -split "`n"
      $hasTrailingNewline = $text.EndsWith("`n")
      $completeLineCount = $lines.Count - 1
      if ($hasTrailingNewline) { $completeLineCount++ }

      for ($i = 0; $i -lt $completeLineCount; $i++) {
        $line = $lines[$i].TrimEnd("`r")
        if ($line.Length -gt 0) { Write-Host "[$Service] $line" -ForegroundColor $Color }
      }

      if ($hasTrailingNewline) {
        $pending = ''
      } else {
        $pending = $lines[$lines.Count - 1]
      }
    }
  } finally {
    $fileStream.Dispose()
  }

  $State["${StreamName}Offset"] = $offset
  $State["${StreamName}Pending"] = $pending

  if ($Flush -and $pending.Length -gt 0) {
    Write-Host "[$Service] $pending" -ForegroundColor $Color
    $State["${StreamName}Pending"] = ''
  }
}

function Stop-ProcessTree {
  param([System.Diagnostics.Process]$Process)

  if (-not $Process) { return }

  $processIds = New-Object 'System.Collections.Generic.List[int]'
  $processIds.Add($Process.Id)
  try {
    $allProcesses = Get-CimInstance -ClassName Win32_Process
    $foundDescendant = $true
    while ($foundDescendant) {
      $foundDescendant = $false
      foreach ($candidate in $allProcesses) {
        if ($processIds.Contains([int]$candidate.ParentProcessId) -and
            -not $processIds.Contains([int]$candidate.ProcessId)) {
          $processIds.Add([int]$candidate.ProcessId)
          $foundDescendant = $true
        }
      }
    }
  } catch {
    Write-Warning "Không truy vấn được cây tiến trình; chỉ dừng tiến trình PID $($Process.Id). $($_.Exception.Message)"
  }

  for ($i = $processIds.Count - 1; $i -ge 0; $i--) {
    Stop-Process -Id $processIds[$i] -Force -ErrorAction SilentlyContinue
  }
}

$SessionId = [Guid]::NewGuid().ToString('N')
$LogPrefix = Join-Path $env:TEMP "idea2video-$SessionId"
$BackendOut = "$LogPrefix-backend.out.log"
$BackendErr = "$LogPrefix-backend.err.log"
$WebOut = "$LogPrefix-web.out.log"
$WebErr = "$LogPrefix-web.err.log"
$BackendProcess = $null
$WebProcess = $null
$ExitCode = 0
$LogState = @{
  BackendOutOffset = [long]0
  BackendOutPending = ''
  BackendErrOffset = [long]0
  BackendErrPending = ''
  WebOutOffset = [long]0
  WebOutPending = ''
  WebErrOffset = [long]0
  WebErrPending = ''
}

try {
  [System.IO.File]::WriteAllText($BackendOut, '')
  [System.IO.File]::WriteAllText($BackendErr, '')
  [System.IO.File]::WriteAllText($WebOut, '')
  [System.IO.File]::WriteAllText($WebErr, '')

  $env:PYTHONUTF8 = '1'
  $BackendProcess = Start-Process `
    -FilePath $Python `
    -ArgumentList '-u -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000' `
    -WorkingDirectory $Backend `
    -RedirectStandardOutput $BackendOut `
    -RedirectStandardError $BackendErr `
    -NoNewWindow `
    -PassThru

  $WebProcess = Start-Process `
    -FilePath $NodeCommand.Source `
    -ArgumentList "`"$Vite`" --host 127.0.0.1" `
    -WorkingDirectory $Web `
    -RedirectStandardOutput $WebOut `
    -RedirectStandardError $WebErr `
    -NoNewWindow `
    -PassThru

  Write-Host 'Đang chạy ứng dụng. Nhấn Ctrl+C để dừng cả backend và frontend.' -ForegroundColor Cyan
  Write-Host 'Web UI: http://127.0.0.1:5173 | API: http://127.0.0.1:8000/docs' -ForegroundColor Cyan

  Start-Sleep -Seconds 2
  try {
    Start-Process 'http://127.0.0.1:5173' | Out-Null
  } catch {
    Write-Warning "Không mở được trình duyệt tự động: $($_.Exception.Message)"
  }

  while ($true) {
    Write-NewLogLines $BackendOut 'backend' Gray $LogState 'BackendOut'
    Write-NewLogLines $BackendErr 'backend' Red $LogState 'BackendErr'
    Write-NewLogLines $WebOut 'web' Gray $LogState 'WebOut'
    Write-NewLogLines $WebErr 'web' Red $LogState 'WebErr'

    $BackendProcess.Refresh()
    $WebProcess.Refresh()
    if ($BackendProcess.HasExited) {
      $ExitCode = 1
      Write-Host 'Backend đã dừng ngoài dự kiến.' -ForegroundColor Red
      break
    }
    if ($WebProcess.HasExited) {
      $ExitCode = 1
      Write-Host 'Frontend đã dừng ngoài dự kiến.' -ForegroundColor Red
      break
    }

    Start-Sleep -Milliseconds 200
  }
} finally {
  Write-NewLogLines $BackendOut 'backend' Gray $LogState 'BackendOut' -Flush
  Write-NewLogLines $BackendErr 'backend' Red $LogState 'BackendErr' -Flush
  Write-NewLogLines $WebOut 'web' Gray $LogState 'WebOut' -Flush
  Write-NewLogLines $WebErr 'web' Red $LogState 'WebErr' -Flush

  Stop-ProcessTree $BackendProcess
  Stop-ProcessTree $WebProcess
  Remove-Item $BackendOut, $BackendErr, $WebOut, $WebErr -Force -ErrorAction SilentlyContinue
}

if ($ExitCode -ne 0) { exit $ExitCode }

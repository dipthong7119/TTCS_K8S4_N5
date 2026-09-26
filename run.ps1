# run.ps1 - Khởi chạy hệ thống CSMS trên Windows (không dùng Docker)

$ErrorActionPreference = "Stop"

$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$VenvDir = Join-Path $RootDir ".venv"

Write-Host "=== Khởi động hệ thống CSMS ===" -ForegroundColor Cyan

# 1. Kiểm tra môi trường ảo (.venv)
if (-not (Test-Path $VenvDir)) {
    Write-Host "Đang tạo môi trường ảo (.venv)..." -ForegroundColor Yellow
    & python -m venv $VenvDir
}

# 2. Cài đặt các gói phụ thuộc
Write-Host "Cài đặt/cập nhật thư viện từ requirements.txt..." -ForegroundColor Yellow
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
& $PythonExe -m pip install --quiet --upgrade pip
& $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt")

# 3. Kiểm tra file .env
$EnvFile = Join-Path $BackendDir ".env"
$EnvExample = Join-Path $BackendDir ".env.example"
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Write-Host "Không tìm thấy file .env, tạo mới từ .env.example..." -ForegroundColor Yellow
        Copy-Item $EnvExample -Destination $EnvFile
    } else {
        Write-Host "Cảnh báo: Không tìm thấy file .env.example để tạo .env!" -ForegroundColor Red
    }
}

# 4. Chạy Alembic để cập nhật database
Write-Host "Chạy Alembic database migrations..." -ForegroundColor Yellow
Push-Location $BackendDir
try {
    & $PythonExe -m alembic upgrade head
} finally {
    Pop-Location
}

# 5. Khởi động Uvicorn server thông qua run.py
Write-Host "Đang khởi chạy Uvicorn server..." -ForegroundColor Green
Write-Host "Truy cập ứng dụng tại: http://localhost:8000/login" -ForegroundColor Green
& $PythonExe (Join-Path $RootDir "run.py")

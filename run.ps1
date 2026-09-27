# run.ps1 - Khởi chạy hệ thống CSMS trên Windows (không dùng Docker)

$ErrorActionPreference = "Stop"

$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$VenvDir = Join-Path $RootDir ".venv"
$EnvFile = Join-Path $RootDir ".env"
$EnvExample = Join-Path $RootDir ".env.example"
$PreviousEnvFile = $env:CSMS_ENV_FILE
$PreviousDatabaseUrl = $env:DATABASE_URL

function New-ProjectVirtualEnvironment {
    param([switch]$Clear)

    $venvArguments = @("-m", "venv")
    if ($Clear) { $venvArguments += "--clear" }
    $venvArguments += $VenvDir

    # Prefer the Windows Python Launcher: it resolves an installed Python even
    # when this PowerShell session has activated a copied, broken .venv.
    $launcher = Get-Command "py.exe" -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($launcher) {
        & $launcher.Source -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            & $launcher.Source -3 @venvArguments
            if ($LASTEXITCODE -ne 0) {
                throw "Không tạo được .venv bằng Python Launcher. Hãy cài Python 3.11 trở lên rồi chạy lại .\run.ps1."
            }
            return
        }
    }

    # Fallback for installations without `py.exe`. Ignore this project's
    # Scripts directory so `python` cannot resolve to the broken venv itself.
    $previousPath = $env:PATH
    try {
        $scriptsPath = [System.IO.Path]::GetFullPath((Join-Path $VenvDir "Scripts")).TrimEnd('\')
        $usablePath = foreach ($entry in ($previousPath -split [System.IO.Path]::PathSeparator)) {
            if ([string]::IsNullOrWhiteSpace($entry)) { continue }
            try {
                $entryPath = [System.IO.Path]::GetFullPath($entry.Trim('"')).TrimEnd('\')
                if (-not $entryPath.Equals($scriptsPath, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $entry
                }
            } catch {
                $entry
            }
        }
        $env:PATH = $usablePath -join [System.IO.Path]::PathSeparator
        $python = Get-Command "python.exe" -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if (-not $python) {
            throw "Không tìm thấy Python hệ thống. Hãy cài Python 3.11 trở lên, chọn Add Python to PATH, rồi chạy lại .\run.ps1."
        }

        & $python.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Python tìm thấy trên PATH phải là phiên bản 3.11 trở lên."
        }
        & $python.Source @venvArguments
        if ($LASTEXITCODE -ne 0) {
            throw "Không tạo được .venv. Hãy kiểm tra bản cài Python rồi chạy lại .\run.ps1."
        }
    } finally {
        $env:PATH = $previousPath
    }
}

Write-Host "=== Khởi động hệ thống CSMS ===" -ForegroundColor Cyan

try {
# 1. Kiểm tra .venv. Virtualenv không thể chép nguyên trạng sang máy khác;
#    pyvenv.cfg có thể vẫn trỏ tới Python ở đường dẫn của máy cũ.
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$VenvIsUsable = $false
if (Test-Path $PythonExe -PathType Leaf) {
    try {
        & $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) and sys.prefix != sys.base_prefix else 1)" 2>$null
        $VenvIsUsable = ($LASTEXITCODE -eq 0)
    } catch {
        $VenvIsUsable = $false
    }
}

if (-not $VenvIsUsable) {
    if (Test-Path $VenvDir) {
        Write-Host ".venv không hợp lệ hoặc được chép từ máy khác; đang tạo lại..." -ForegroundColor Yellow
        New-ProjectVirtualEnvironment -Clear
    } else {
        Write-Host "Đang tạo môi trường ảo (.venv)..." -ForegroundColor Yellow
        New-ProjectVirtualEnvironment
    }
}

# 2. Khởi tạo pip từ Python cục bộ, sau đó cài dependencies của dự án.
Write-Host "Cài đặt/cập nhật thư viện từ requirements.txt..." -ForegroundColor Yellow
& $PythonExe -m ensurepip --upgrade --default-pip
if ($LASTEXITCODE -ne 0) { throw "Không khởi tạo được pip trong .venv mới." }
& $PythonExe -m pip --disable-pip-version-check install -r (Join-Path $BackendDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Không cài được thư viện. Hãy kiểm tra Internet hoặc proxy để tải package từ PyPI, rồi chạy lại .\run.ps1."
}

# 3. Dùng chung cấu hình ở thư mục gốc cho cả Docker và chạy local
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Write-Host "Không tìm thấy file .env, tạo mới từ .env.example..." -ForegroundColor Yellow
        Copy-Item $EnvExample -Destination $EnvFile
    } else {
        throw "Không tìm thấy .env hoặc .env.example ở thư mục dự án."
    }
}
$env:CSMS_ENV_FILE = $EnvFile
$env:DATABASE_URL = "sqlite:///./csms.db"

# 4. Chạy Alembic để cập nhật database
Write-Host "Chạy Alembic database migrations..." -ForegroundColor Yellow
Push-Location $BackendDir
try {
    & $PythonExe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Alembic migration thất bại." }
} finally {
    Pop-Location
}

# 5. Khởi động Uvicorn server thông qua run.py
Write-Host "Đang khởi chạy Uvicorn server..." -ForegroundColor Green
Write-Host "Truy cập ứng dụng tại: http://localhost:8000/login" -ForegroundColor Green
& $PythonExe (Join-Path $RootDir "run.py")
if ($LASTEXITCODE -ne 0) { throw "Ứng dụng kết thúc với mã lỗi $LASTEXITCODE." }
} finally {
    if ($null -eq $PreviousEnvFile) {
        Remove-Item Env:\CSMS_ENV_FILE -ErrorAction SilentlyContinue
    } else {
        $env:CSMS_ENV_FILE = $PreviousEnvFile
    }
    if ($null -eq $PreviousDatabaseUrl) {
        Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
    } else {
        $env:DATABASE_URL = $PreviousDatabaseUrl
    }
}

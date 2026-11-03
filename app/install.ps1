param([string]$Python = 'python', [switch]$WithVector60)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & $Python -c "import sys, tkinter; assert sys.version_info >= (3,12), 'Python 3.12 or newer is required'"
    if ($LASTEXITCODE -ne 0) { throw 'Install Python with Tcl/Tk support first.' }
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
    $requirements = if ($WithVector60) { 'requirements-vector60.txt' } else { 'requirements.txt' }
    & '.\.venv\Scripts\python.exe' -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    Write-Host 'Installation complete. Run Run.cmd (or Run.cmd --demo).'
} finally { Pop-Location }

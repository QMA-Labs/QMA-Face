$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory '.venv/Scripts/python.exe'
if ($env:QMA_FACE_PYTHON) { $pythonExecutable = $env:QMA_FACE_PYTHON }
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Create .venv and install the project first. See README.md.'
}
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $projectDirectory
& $pythonExecutable -m qma_face
exit $LASTEXITCODE

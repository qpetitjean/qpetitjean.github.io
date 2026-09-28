$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskQuarto = Get-Command quarto -ErrorAction SilentlyContinue
if ($taskQuarto) { $taskQuartoPath = $taskQuarto.Source }
elseif (Test-Path -LiteralPath 'C:/Program Files/RStudio/resources/app/bin/quarto/bin/quarto.exe') { $taskQuartoPath = 'C:/Program Files/RStudio/resources/app/bin/quarto/bin/quarto.exe' }
else { throw 'Install Quarto or add its executable to PATH.' }
if (-not $env:QUARTO_PYTHON) {
    $taskBundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $taskBundledPython) { $env:QUARTO_PYTHON = $taskBundledPython }
}
$env:PYTHONIOENCODING = 'utf-8'
Push-Location -LiteralPath $taskRoot
try { & $taskQuartoPath preview --port 4321 --no-browser }
finally { Pop-Location }


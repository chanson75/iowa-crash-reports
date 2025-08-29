# run_scraper.ps1
# Activates the venv (PowerShell) and runs main.py, capturing stdout/stderr to run.log
# Usage: double-click, or Task Scheduler action -> powershell.exe -File "C:\path\run_scraper.ps1"

param(
    [string] $ProjectDir = "$PSScriptRoot"
)

# move to project dir
Set-Location -Path $ProjectDir

# Activate venv
$activate = Join-Path $ProjectDir ".venv\Scripts\Activate.ps1"
if (-Not (Test-Path $activate)) {
    Write-Error "Activate.ps1 not found at $activate. Ensure .venv exists."
    exit 1
}

. $activate

# Run scraper and append to run.log (keeps history)
$log = Join-Path $ProjectDir "run.log"
python .\main.py >> $log 2>&1
$exitCode = $LASTEXITCODE

# optional: write a short timestamped line for easier scanning
"{0} - exit {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $exitCode | Out-File -FilePath $log -Append

exit $exitCode

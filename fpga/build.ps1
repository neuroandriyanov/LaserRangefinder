param([string]$QuartusRoot = $env:QUARTUS_ROOTDIR)
$ErrorActionPreference = 'Stop'
if ($QuartusRoot) {
    $candidates = @(
        (Join-Path $QuartusRoot 'bin64/quartus_sh.exe'),
        (Join-Path $QuartusRoot 'quartus/bin64/quartus_sh.exe'),
        (Join-Path $QuartusRoot 'bin/quartus_sh.exe')
    )
    $compiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
} else {
    $command = Get-Command quartus_sh -ErrorAction SilentlyContinue
    $compiler = if ($command) { $command.Source } else { $null }
}
if (-not $compiler) { throw 'Quartus was not found. Set QUARTUS_ROOTDIR or pass -QuartusRoot.' }
$timing = Join-Path (Split-Path $compiler) 'quartus_sta.exe'
Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Path test-results -Force | Out-Null
    & $compiler --flow compile DistanceSensorFpga_v0
    if ($LASTEXITCODE -ne 0) { throw 'Quartus compilation failed.' }
    & $timing -t tools/report_config_timing.tcl
    if ($LASTEXITCODE -ne 0) { throw 'Timing report generation failed.' }
    Write-Host 'Build complete. Inspect output_files/*.sta.summary and test-results/config-unconstrained.rpt.'
    Write-Host 'No hardware was programmed.'
} finally { Pop-Location }

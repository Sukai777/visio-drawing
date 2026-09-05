#requires -Version 7.0
param(
    [Parameter(Mandatory=$true)][string]$Python,
    [string]$OutputDirectory,
    [switch]$TestTransforms
)
$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repositoryRoot '.build/rf-lna' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
$evidenceLock = Join-Path $OutputDirectory 'source.lock.json'
$drawingScript = Join-Path $repositoryRoot 'scripts/drawing.py'
if (-not (Test-Path -LiteralPath $evidenceLock)) {
    & $Python $drawingScript record --evidence (Join-Path $PSScriptRoot 'source.json') --lock $evidenceLock
    if ($LASTEXITCODE -ne 0) { throw 'Evidence recording failed.' }
}
& (Join-Path $repositoryRoot 'scripts/run.ps1') `
    -Model (Join-Path $PSScriptRoot 'model.json') `
    -Lock $evidenceLock `
    -Output (Join-Path $OutputDirectory 'RF_LNA.vsdx') `
    -Python $Python `
    -TestTransforms:$TestTransforms

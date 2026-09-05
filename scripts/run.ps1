#requires -Version 7.0
param(
    [Parameter(Mandatory=$true)][string]$Model,
    [Parameter(Mandatory=$true)][string]$Lock,
    [Parameter(Mandatory=$true)][string]$Output,
    [Parameter(Mandatory=$true)][string]$Python,
    [switch]$TestTransforms
)
$ErrorActionPreference='Stop'
if(-not (Test-Path -LiteralPath $Python -PathType Leaf)){throw 'Pass the actual Python executable, not a Windows Store alias.'}
& $Python -c 'import sys; assert sys.version_info >= (3,10); import PIL'
if($LASTEXITCODE -ne 0){throw 'Python 3.10+ with Pillow is required for comparison images.'}
$Output=[IO.Path]::GetFullPath($Output)
$stem=Join-Path (Split-Path -Parent $Output) ([IO.Path]::GetFileNameWithoutExtension($Output))
$compiled=$stem+'.compiled.json'
& $Python (Join-Path $PSScriptRoot 'drawing.py') prepare --model $Model --lock $Lock --out $compiled
if($LASTEXITCODE -ne 0){throw 'Source/model preflight failed.'}
& (Join-Path $PSScriptRoot 'render-native.ps1') -Model $compiled -Output $Output -TestTransforms:$TestTransforms
& $Python (Join-Path $PSScriptRoot 'drawing.py') verify --compiled $compiled --vsdx $Output
if($LASTEXITCODE -ne 0){throw 'Saved native drawing verification failed.'}
& $Python (Join-Path $PSScriptRoot 'drawing.py') compare --compiled $compiled --rendered ($stem+'.png') --out ($stem+'.review')
if($LASTEXITCODE -ne 0){throw 'Regional comparison generation failed.'}
Write-Output 'Native drawing ready. Inspect every regional comparison before filling visual review and finalizing.'

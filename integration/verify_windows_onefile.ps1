param(
    [Parameter(Mandatory=$true)][string]$Delivery,
    [Parameter(Mandatory=$true)][string]$Evidence,
    [Parameter(Mandatory=$true)][string]$ExpectedCommit
)
$ErrorActionPreference = 'Stop'
$exeName = 'Facility Studio 5.7.3.exe'
$source = Join-Path $Delivery $exeName
$records = @(Get-Content (Join-Path $Delivery 'SHA256SUMS.txt') -Encoding utf8)
if ($records.Count -ne 1 -or $records[0] -cnotmatch ('^[0-9a-f]{64}  ' + [regex]::Escape($exeName) + '$')) { throw 'Invalid single-EXE checksum manifest' }
$expectedHash = $records[0].Substring(0,64)
if ((Get-FileHash $source -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expectedHash) { throw 'Downloaded EXE checksum mismatch' }
New-Item -ItemType Directory $Evidence | Out-Null
$Evidence = (Resolve-Path $Evidence).Path
# Each execution directory contains only the EXE; all data and results are outside it.
$launch = Join-Path $env:RUNNER_TEMP ('單檔空目錄 Ω ' + [guid]::NewGuid())
New-Item -ItemType Directory $launch | Out-Null
$exe = Join-Path $launch $exeName
Copy-Item $source $exe
$env:FACILITY_STUDIO_FUSION_DATA = Join-Path $Evidence '隔離測試資料'
$env:FACILITY_TEST_BLOCK_NETWORK = '1'
$env:FACILITY_CAPTURE_SYNTHETIC_UI = '1'
$oldPath = $env:PATH
$oldPythonPath = $env:PYTHONPATH
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
$env:PYTHONPATH = ''
$env:PYTHONHOME = ''
try {
    if (@(Get-ChildItem $launch -Force).Count -ne 1) { throw 'Launch directory is not single-file' }
    foreach ($suite in @('fusion', 'facilities')) {
        $result = Join-Path $Evidence ($suite + '.json')
        $p = Start-Process -FilePath $exe -WorkingDirectory $launch -ArgumentList @("--$suite-self-test", "`"$result`"") -PassThru
        if (-not $p.WaitForExit(300000)) { Stop-Process -Id $p.Id -Force; throw "$suite timed out" }
        if ($p.ExitCode -ne 0) { throw "$suite exited $($p.ExitCode)" }
        $r = Get-Content $result -Raw -Encoding utf8 | ConvertFrom-Json
        if ($r.passed -ne $true -or $r.frozen -ne $true -or $r.build_commit -cne $ExpectedCommit -or $r.suite -cne $suite) { throw "$suite identity/acceptance mismatch" }
        if (@($r.checks).Count -eq 0 -or @($r.checks | Where-Object { $_.passed -ne $true }).Count -ne 0) { throw "$suite checks failed" }
    }
    # Start with no arguments, as a double-click would, and observe an actual window.
    $p = Start-Process -FilePath $exe -WorkingDirectory $launch -PassThru
    $window = $null
    $deadline = [datetime]::UtcNow.AddSeconds(180)
    do {
        Start-Sleep -Seconds 2
        $window = Get-Process | Where-Object { $_.Path -eq $exe -and $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match 'Facility Studio|廠務簡易工具|廠務工程工作台' } | Select-Object -First 1
    } until ($window -or [datetime]::UtcNow -ge $deadline)
    if (-not $window) { throw 'No normal-launch product window appeared' }
    $title = $window.MainWindowTitle
    if (-not $window.CloseMainWindow()) { throw 'Could not request normal GUI close' }
    if (-not $p.WaitForExit(30000) -or $p.ExitCode -ne 0) { throw 'Normal GUI close did not exit cleanly' }
    if (@(Get-ChildItem $launch -Force).Count -ne 1 -or (Get-ChildItem $launch -Force).Name -cne $exeName) { throw 'Application created adjacent runtime files' }
    if ((Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expectedHash) { throw 'Executable changed during verification' }
    $signature = Get-AuthenticodeSignature $exe
    @{passed=$true; commit=$ExpectedCommit; sha256=$expectedHash; host=$env:RUNNER_OS; image=$env:ImageOS; os=[Environment]::OSVersion.VersionString; singleExeInUnicodeDirectory=$true; externalPythonPathRemoved=$true; adjacentResourcesRequired=$false; applicationNetworkAuditBlocked=$true; normalNoArgumentsGuiLaunch=$true; normalGuiTitle=$title; cleanGuiExit=$true; authenticodeStatus=$signature.Status.ToString(); signerSubject=$(if ($signature.SignerCertificate) {$signature.SignerCertificate.Subject} else {$null}); trustedSigningClaimed=$false} |
        ConvertTo-Json | Set-Content (Join-Path $Evidence 'Single_File_Verification.json') -Encoding utf8
} finally {
    Get-Process | Where-Object { $_.Path -eq $exe } | Stop-Process -Force -ErrorAction SilentlyContinue
    $env:PATH = $oldPath
    $env:PYTHONPATH = $oldPythonPath
}

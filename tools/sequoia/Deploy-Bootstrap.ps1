param(
    [Parameter(Mandatory=$true)][string]$Plan,
    [Parameter(Mandatory=$true)][string]$BackupManifest,
    [Parameter(Mandatory=$true)][string]$Prepared,
    [Parameter(Mandatory=$true)][string]$Report
)
# Copies only Sequoia-Prep/ onto the identified external ESP. Live EFI unchanged.
$ErrorActionPreference='Stop'
$mounted=$false
$access=$null
try {
    $planData=Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
    $backup=Get-Content -LiteralPath $BackupManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $packageRoot=[IO.Path]::GetFullPath($Prepared).TrimEnd('\')
    $files=Get-Content -LiteralPath (Join-Path $packageRoot 'deployment-files.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($backup.status -ne 'complete' -or $backup.sourceAccess -ne 'read-only') {throw 'Verified EFI/GPT backup is required.'}
    if ($backup.sourcePlan.disk.serial -ne $planData.disk.serial -or $backup.sourcePlan.disk.bytes -ne $planData.disk.bytes) {throw 'Backup identifies another disk.'}
    if ($backup.sourcePlan.target.guid -ne $planData.target.guid -or $backup.sourcePlan.target.offset -ne $planData.target.offset -or $backup.sourcePlan.target.bytes -ne $planData.target.bytes) {throw 'Backup identifies another target region.'}
    if ($backup.userRequestedNoTahoeBackup -ne $true -or $backup.systemImageIncluded -ne $false) {throw 'Expected the explicit user-selected no-system-image policy.'}
    foreach($regionName in @('gpt-first-1MiB','gpt-last-1MiB','external-esp')) {
        $region=@($backup.regions | Where-Object {$_.name -eq $regionName})
        if ($region.Count -ne 1 -or $region[0].decompressedVerification -ne 'passed') {throw 'EFI/GPT backup verification is incomplete.'}
    }
    $disks=@(Get-Disk | Where-Object {([string]$_.SerialNumber).Trim() -eq $planData.disk.serial -and $_.Size -eq $planData.disk.bytes})
    if ($disks.Count -ne 1 -or $disks[0].IsBoot -or $disks[0].IsSystem) {throw 'External SSD identity mismatch.'}
    $disk=$disks[0]
    $parts=@(Get-Partition -DiskNumber $disk.Number)
    foreach ($expected in @($planData.esp,$planData.protected,$planData.target)) {
        $match=@($parts | Where-Object {$_.Guid.Trim('{}').ToLower() -eq $expected.guid.ToLower()})
        if ($match.Count -ne 1 -or $match[0].Offset -ne $expected.offset -or $match[0].Size -ne $expected.bytes) {throw 'Partition identity/layout changed.'}
    }
    $esp=@($parts | Where-Object {$_.Guid.Trim('{}').ToLower() -eq $planData.esp.guid.ToLower()})[0]
    $available=@(80..90 | ForEach-Object {[char]$_} | Where-Object {-not (Get-PSDrive -Name ([string]$_) -ErrorAction SilentlyContinue)})
    if (-not $available.Count) {throw 'No temporary drive letter available.'}
    $access=([string]$available[-1])+':\'
    Add-PartitionAccessPath -DiskNumber $disk.Number -PartitionNumber $esp.PartitionNumber -AccessPath $access
    $mounted=$true
    $dest=Join-Path $access 'Sequoia-Prep'
    if (Test-Path -LiteralPath $dest) {throw 'Sequoia-Prep already exists; refusing overwrite.'}
    $efiMeta=Get-Content -LiteralPath (Join-Path $packageRoot 'efi-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $liveConfig=Join-Path $access 'EFI\OC\config.plist'
    if ((Get-FileHash -LiteralPath $liveConfig -Algorithm SHA256).Hash.ToLower() -ne $efiMeta.sourceConfigSha256) {throw 'Live EFI config changed since source backup.'}
    $needed=0L
    foreach($file in $files) {
        $source=[IO.Path]::GetFullPath((Join-Path $packageRoot $file.path))
        if (-not $source.StartsWith($packageRoot+'\',[StringComparison]::OrdinalIgnoreCase)) {throw 'File path escapes package.'}
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower() -ne $file.sha256) {throw 'Prepared file checksum mismatch.'}
        $needed+=[int64]$file.bytes
    }
    if ([IO.DriveInfo]::new($access).AvailableFreeSpace -lt $needed+8MB) {throw 'Not enough ESP space; no existing files will be removed.'}
    New-Item -ItemType Directory -Path $dest | Out-Null
    foreach($file in $files) {
        $source=Join-Path $packageRoot $file.path
        $target=Join-Path $dest $file.path
        $parent=[IO.Path]::GetDirectoryName($target)
        if (-not (Test-Path -LiteralPath $parent)) {New-Item -ItemType Directory -Path $parent -Force | Out-Null}
        Copy-Item -LiteralPath $source -Destination $target
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower() -ne $file.sha256) {throw 'Copied file checksum mismatch.'}
    }
    if ((Get-FileHash -LiteralPath $liveConfig -Algorithm SHA256).Hash.ToLower() -ne $efiMeta.sourceConfigSha256) {throw 'Live config changed during copy.'}
    @{status='complete';files=$files.Count;bytes=$needed;destination='External ESP / Sequoia-Prep';liveEfiConfigUnchanged=$true;apfsPartitionsWritten=$false} |
        ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding UTF8
} catch {
    @{status='failed';error=$_.Exception.Message} | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding UTF8
    exit 1
} finally {
    if ($mounted) {Remove-PartitionAccessPath -DiskNumber $disk.Number -PartitionNumber $esp.PartitionNumber -AccessPath $access}
}

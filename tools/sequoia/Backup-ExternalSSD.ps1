param(
    [Parameter(Mandatory=$true)][string]$Plan,
    [Parameter(Mandatory=$true)][string]$Destination,
    [Parameter(Mandatory=$true)][string]$Python,
    [switch]$IncludeSystemImage
)
# Elevated, READ-ONLY access to the identified source disk. Writes backup files only.
$ErrorActionPreference = 'Stop'
$planData = Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
$destPath = [IO.Path]::GetFullPath($Destination)
$statusFile = Join-Path $destPath 'backup-status.json'
function Save-Status($value) {
    $value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statusFile -Encoding UTF8
}
try {
    if (-not [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Windows administrator access is required to read raw disk sectors.'
    }
    if (Test-Path -LiteralPath $destPath) { throw 'Backup destination already exists; refusing overwrite.' }
    New-Item -ItemType Directory -Path $destPath | Out-Null
    $disks = @(Get-Disk | Where-Object {
        ([string]$_.SerialNumber).Trim() -eq $planData.disk.serial -and $_.Size -eq $planData.disk.bytes
    })
    if ($disks.Count -ne 1 -or $disks[0].IsBoot -or $disks[0].IsSystem) { throw 'Source disk identity/role mismatch.' }
    $disk = $disks[0]
    if ($disk.PartitionStyle -ne 'GPT') { throw 'Source must be GPT.' }
    $parts = @(Get-Partition -DiskNumber $disk.Number)
    foreach ($expected in @($planData.esp, $planData.protected, $planData.target)) {
        $match = @($parts | Where-Object { $_.Guid.Trim('{}').ToLower() -eq $expected.guid.ToLower() })
        if ($match.Count -ne 1 -or $match[0].Offset -ne $expected.offset -or $match[0].Size -ne $expected.bytes) {
            throw 'Partition identity, offset or length changed.'
        }
    }
    $target = @($parts | Where-Object { $_.Guid.Trim('{}').ToLower() -eq $planData.target.guid.ToLower() })[0]
    if (@($target.AccessPaths | Where-Object { $_ }).Count -ne 0) { throw 'Target APFS must not be mounted in Windows.' }
    $drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($destPath))
    $requiredBytes=[int64]$planData.esp.bytes+1GB
    if ($IncludeSystemImage) {$requiredBytes=[int64]$planData.target.bytes+10GB}
    if ($drive.AvailableFreeSpace -lt $requiredBytes) { throw 'Insufficient local backup space.' }
    $sourcePath = '\\.\PhysicalDrive' + $disk.Number
    Save-Status @{status='running';stage='starting';sourceAccess='read-only';protectedPartitionWritten=$false}
    if (-not (Test-Path -LiteralPath $Python)) { throw 'Pinned Python runtime not found.' }
    $regions = @(
        @{name='gpt-first-1MiB';offset=0L;bytes=1MB},
        @{name='gpt-last-1MiB';offset=([int64]$disk.Size-1MB);bytes=1MB},
        @{name='external-esp';offset=[int64]$planData.esp.offset;bytes=[int64]$planData.esp.bytes}
    )
    if ($IncludeSystemImage) {$regions+=@{name='tahoe-apfs-physical-store';offset=[int64]$planData.target.offset;bytes=[int64]$planData.target.bytes}}
    $results = @()
    foreach ($region in $regions) {
        Save-Status @{status='running';stage=$region.name;sourceAccess='read-only';protectedPartitionWritten=$false}
        $file = Join-Path $destPath ($region.name + '.raw.zst')
        & $Python -u (Join-Path $PSScriptRoot 'backup_ranges.py') $sourcePath $region.offset $region.bytes $file (Join-Path $destPath 'progress.json')
        if ($LASTEXITCODE -ne 0) { throw 'Read-only backup helper failed.' }
        $result = Get-Content -LiteralPath ($file + '.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $results += @{name=$region.name;file=$result.file;offset=$region.offset;rawBytes=$region.bytes;rawSha256=$result.rawSha256;compressedSha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower();decompressedVerification=$result.decompressedVerification;codec='zstd-level-1'}
    }
    $afterDisk = @(Get-Disk | Where-Object { ([string]$_.SerialNumber).Trim() -eq $planData.disk.serial -and $_.Size -eq $planData.disk.bytes })
    if ($afterDisk.Count -ne 1) { throw 'Source disk no longer uniquely identified.' }
    $after = @(Get-Partition -DiskNumber $afterDisk[0].Number)
    foreach ($expected in @($planData.esp,$planData.protected,$planData.target)) {
        $match=@($after | Where-Object { $_.Guid.Trim('{}').ToLower() -eq $expected.guid.ToLower() })
        if ($match.Count -ne 1 -or $match[0].Offset -ne $expected.offset -or $match[0].Size -ne $expected.bytes) { throw 'Source layout changed during backup.' }
    }
    @{schema=1;status='complete';created=(Get-Date).ToString('o');sourcePlan=$planData;regions=$results;sourceAccess='read-only';systemImageIncluded=[bool]$IncludeSystemImage;userRequestedNoTahoeBackup=($planData.choices.backupTahoeSystem -eq $false);protectedPartitionWritten=$false;restorePerformed=$false} |
        ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $destPath 'backup-manifest.json') -Encoding UTF8
    Save-Status @{status='complete';decompressedVerification='passed';sourceAccess='read-only';systemImageIncluded=[bool]$IncludeSystemImage;protectedPartitionWritten=$false}
} catch {
    if (Test-Path -LiteralPath $destPath) { Save-Status @{status='failed';error=$_.Exception.Message;sourceAccess='read-only'} }
    exit 1
}

param(
    [Parameter(Mandatory=$true)][string]$Prepared,
    [Parameter(Mandatory=$true)][string]$Report
)
# Reversible file copy to the previously authorized USB ESP. Never formats a disk.
$ErrorActionPreference='Stop'
try {
    $root=[IO.Path]::GetFullPath($Prepared).TrimEnd('\')
    $manifest=Get-Content -LiteralPath (Join-Path $root 'recovery-deployment.json') -Raw | ConvertFrom-Json
    $plan=Get-Content -LiteralPath (Join-Path $root 'Sequoia-USB\disk-plan.json') -Raw | ConvertFrom-Json
    $disks=@(Get-Disk | Where-Object {([string]$_.SerialNumber).Trim() -eq $plan.usb.disk.serial -and $_.Size -eq $plan.usb.disk.bytes})
    if($disks.Count -ne 1 -or $disks[0].IsBoot -or $disks[0].IsSystem -or $disks[0].BusType -ne 'USB'){throw 'Approved USB identity changed.'}
    $parts=@(Get-Partition -DiskNumber $disks[0].Number)
    if($parts.Count -ne 2){throw 'USB partition count changed.'}
    foreach($spec in @($plan.usb.esp,$plan.usb.media)) {
        $hits=@($parts | Where-Object {$_.Guid.Trim('{}').ToLower() -eq $spec.guid.ToLower() -and $_.Offset -eq $spec.offset -and $_.Size -eq $spec.bytes})
        if($hits.Count -ne 1){throw 'USB GPT identity/boundary changed.'}
    }
    $esp=$parts | Where-Object {$_.Guid.Trim('{}').ToLower() -eq $plan.usb.esp.guid.ToLower()}
    $espRoot=@($esp.AccessPaths | Where-Object {$_ -match '^[A-Z]:\\$'})[0]
    if(-not $espRoot){throw 'USB ESP has no drive letter.'}
    $espRoot=[IO.Path]::GetFullPath($espRoot)
    foreach($entry in $manifest.files) {
        $source=[IO.Path]::GetFullPath((Join-Path $root $entry.path))
        $dest=[IO.Path]::GetFullPath((Join-Path $espRoot $entry.path))
        if(-not $source.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase) -or -not $dest.StartsWith($espRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Manifest path escapes delivery.'}
        if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower() -ne $entry.sha256){throw 'Recovery source checksum mismatch.'}
    }
    @{status='copying-recovery';usbEsp=$espRoot} | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding UTF8
    foreach($entry in $manifest.files) {
        $source=Join-Path $root $entry.path
        $dest=Join-Path $espRoot $entry.path
        $parent=[IO.Path]::GetDirectoryName($dest)
        if(-not (Test-Path -LiteralPath $parent)){New-Item -ItemType Directory -Path $parent -Force | Out-Null}
        Copy-Item -LiteralPath $source -Destination $dest -Force
        if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLower() -ne $entry.sha256){throw "USB readback mismatch: $($entry.path)"}
    }
    @{status='recovery-files-verified';filesVerified=$manifest.files.Count;usbEsp=$espRoot;nativeBootTested=$false;partitionsModified=$false} | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding UTF8
} catch {
    @{status='failed';error=$_.Exception.Message} | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding UTF8
    exit 1
}

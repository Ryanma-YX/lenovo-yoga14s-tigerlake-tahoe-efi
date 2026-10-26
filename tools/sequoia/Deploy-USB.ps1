param(
    [Parameter(Mandatory=$true)][string]$Prepared,
    [Parameter(Mandatory=$true)][string]$Report
)
# User authorized erasing both existing partitions on the specifically planned USB.
# Preserve GPT boundaries and GUIDs; format only its two partitions, then stage.
$ErrorActionPreference='Stop'
try {
    $root=[IO.Path]::GetFullPath($Prepared).TrimEnd('\')
    $plan=Get-Content -LiteralPath (Join-Path $root 'Sequoia-USB\disk-plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($plan.usb.eraseAllUserAuthorized -ne $true) {throw 'Whole-USB erase authorization missing.'}
    $manifest=Get-Content -LiteralPath (Join-Path $root 'usb-deployment.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    function Find-ApprovedUsb {
        $disks=@(Get-Disk | Where-Object {([string]$_.SerialNumber).Trim() -eq $plan.usb.disk.serial -and $_.Size -eq $plan.usb.disk.bytes})
        if ($disks.Count -ne 1 -or $disks[0].IsBoot -or $disks[0].IsSystem -or $disks[0].BusType -ne 'USB') {throw 'USB identity mismatch.'}
        $disk=$disks[0]
        $parts=@(Get-Partition -DiskNumber $disk.Number)
        if ($parts.Count -ne 2) {throw 'USB partition count changed.'}
        foreach ($spec in @($plan.usb.esp,$plan.usb.media)) {
            $hits=@($parts | Where-Object {$_.Guid.Trim('{}').ToLower() -eq $spec.guid.ToLower() -and $_.Offset -eq $spec.offset -and $_.Size -eq $spec.bytes})
            if ($hits.Count -ne 1) {throw 'USB partition identity/layout mismatch.'}
        }
        return $disk
    }
    function Check-ProtectedSsd {
        $ssd=@(Get-Disk | Where-Object {([string]$_.SerialNumber).Trim() -eq $plan.disk.serial -and $_.Size -eq $plan.disk.bytes})
        if ($ssd.Count -ne 1 -or $ssd[0].IsBoot -or $ssd[0].IsSystem) {throw 'SSK identity changed.'}
        $parts=@(Get-Partition -DiskNumber $ssd[0].Number)
        foreach ($spec in @($plan.esp,$plan.protected,$plan.target)) {
            $hits=@($parts | Where-Object {$_.Guid.Trim('{}').ToLower() -eq $spec.guid.ToLower() -and $_.Offset -eq $spec.offset -and $_.Size -eq $spec.bytes})
            if ($hits.Count -ne 1) {throw 'Protected SSK layout changed.'}
        }
    }
    # Source verification is complete before destructive formatting starts.
    foreach ($file in $manifest.files) {
        $source=[IO.Path]::GetFullPath((Join-Path $root $file.path))
        if (-not $source.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) {throw 'Source escapes package root.'}
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower() -ne $file.sha256) {throw 'Source checksum mismatch.'}
    }
    if ((Get-FileHash -LiteralPath $manifest.installerSource -Algorithm SHA256).Hash.ToLower() -ne $manifest.installerSha256) {throw 'Full installer checksum mismatch.'}
    Check-ProtectedSsd
    $disk=Find-ApprovedUsb
    @{status='formatting-approved-usb';serial=$plan.usb.disk.serial} | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding UTF8
    foreach ($spec in @($plan.usb.esp,$plan.usb.media)) {
        $disk=Find-ApprovedUsb
        $part=Get-Partition -DiskNumber $disk.Number | Where-Object {$_.Guid.Trim('{}').ToLower() -eq $spec.guid.ToLower()}
        $isEsp=$spec.guid -eq $plan.usb.esp.guid
        $fs=if($isEsp){'FAT32'}else{'NTFS'}
        $label=if($isEsp){'SEQ-BOOT'}else{'SEQ-STAGE'}
        Format-Volume -Partition $part -FileSystem $fs -NewFileSystemLabel $label -Force -Confirm:$false | Out-Null
    }
    $disk=Find-ApprovedUsb
    $esp=Get-Partition -DiskNumber $disk.Number | Where-Object {$_.Guid.Trim('{}').ToLower() -eq $plan.usb.esp.guid.ToLower()}
    $media=Get-Partition -DiskNumber $disk.Number | Where-Object {$_.Guid.Trim('{}').ToLower() -eq $plan.usb.media.guid.ToLower()}
    $espPath=@($esp.AccessPaths | Where-Object {$_ -match '^[A-Z]:\\$'})[0]
    $mediaPath=@($media.AccessPaths | Where-Object {$_ -match '^[A-Z]:\\$'})[0]
    if (-not $espPath -or -not $mediaPath) {throw 'USB drive letters unavailable after formatting.'}
    foreach ($file in $manifest.files) {
        $source=Join-Path $root $file.path
        $target=Join-Path $espPath $file.path
        $parent=[IO.Path]::GetDirectoryName($target)
        if (-not (Test-Path -LiteralPath $parent)) {New-Item -ItemType Directory -Path $parent -Force | Out-Null}
        Copy-Item -LiteralPath $source -Destination $target
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower() -ne $file.sha256) {throw 'USB EFI copy checksum mismatch.'}
    }
    @{status='copying-full-installer';efiFilesVerified=$manifest.files.Count;source=$manifest.installerSource} | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding UTF8
    $destination=Join-Path $mediaPath 'InstallAssistant.pkg'
    Copy-Item -LiteralPath $manifest.installerSource -Destination $destination
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLower() -ne $manifest.installerSha256) {throw 'USB installer copy checksum mismatch.'}
    Check-ProtectedSsd
    $null=Find-ApprovedUsb
    @{status='windows-usb-staging-complete';efiFilesVerified=$manifest.files.Count;installerBytes=(Get-Item -LiteralPath $destination).Length;
        installerSha256=$manifest.installerSha256;usbBoot=$espPath;usbStage=$mediaPath;sskLayoutUnchanged=$true;
        macosCreateinstallmediaPending=$true} | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding UTF8
} catch {
    @{status='failed';error=$_.Exception.Message} | ConvertTo-Json | Set-Content -LiteralPath $Report -Encoding UTF8
    exit 1
}

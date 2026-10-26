"""Build a PRIVATE standalone USB delivery; never add its output to Git."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preparation', required=True, type=Path)
    parser.add_argument('--usb-layout', required=True, type=Path)
    args = parser.parse_args()
    base = args.preparation.resolve()
    root = base / 'Prepared' / 'USB-Delivery'
    root.mkdir()  # Do not silently replace a previous private delivery.
    here = Path(__file__).resolve().parent
    setup = root / 'Sequoia-USB'
    setup.mkdir()
    old = base / 'Prepared' / 'Delivery'
    efi = base / 'Prepared' / 'EFI-private'
    for name in ('Boot', 'OC'):
        shutil.copytree(efi / name, root / 'EFI' / name)
    shutil.copytree(old / 'EFI', setup / 'EFI')
    shutil.copytree(old / 'EFI-profiles', setup / 'EFI-profiles')
    for name in ('efi-manifest.json', 'installer-verified.json', 'installer-selected.json', 'installer-xar-signature.json'):
        shutil.copy2(old / name, setup / name)
    for name in ('mac_disk_guard.js', 'Start-USB.command', 'Prepare-USB.command',
                 'Set-SSD-USB-Profile.command', 'Finish-Sequoia-USB.command'):
        shutil.copy2(here / name, setup / name)
    shutil.copy2(here / 'Show-USB-Install-Target.command', setup / 'Show-Install-Target.command')
    plan = load(base / 'Private' / 'disk-plan.json')
    plan['choices'].update(extraMedia=True, temporaryInstallerPartitionWithinTargetRegion=False)
    plan['usb'] = load(args.usb_layout)
    assert plan['usb']['eraseAllUserAuthorized'] is True
    (setup / 'disk-plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    graphics = base / 'Private' / 'fresh-esp' / 'Tahoe-Setup' / 'WhateverXe-Graphics-0.2.0.pkg'
    assert sha(graphics) == 'a70cca1fa5f085923be40ed346875c7a042bb002f5b87f57f0d2ef0ee35e6e4a'
    (setup / 'Payloads').mkdir()
    shutil.copy2(graphics, setup / 'Payloads' / graphics.name)
    esp_uuid = plan['usb']['esp']['guid']
    steps = f'''# SanDisk 完整安装盘路线

本目录含真实机器身份，只保留本地。原 SSK 的约 239GB Tahoe 区域是唯一系统替换目标；约 273GB 数据区及内部 Windows 盘保留。

## 1. 进入现有 Tahoe 制作介质

同时插着 SSK 与 SanDisk。在 Tahoe 终端执行：

```bash
sudo diskutil mount {esp_uuid}
USB_BOOT="$(diskutil info -plist {esp_uuid} | plutil -extract MountPoint raw -o - -)"
bash "$USB_BOOT/Sequoia-USB/Start-USB.command"
```

查看进度：

```bash
tail -f /Users/Shared/Sequoia-USB-Preparation-20261026/launcher.log
```

完整 InstallAssistant.pkg 已放在 SanDisk 的 NTFS 数据分区，脚本校验后将安装 app 展开到 Tahoe。随后只格式化 SanDisk 数据分区、调用 Apple createinstallmedia，保留其 EFI。SSK 不缩容，当前 EFI 不更新。等待 EXTERNAL_USB_MEDIA_READY 才重启。macOS 原生阶段仍待实测；出错保留日志并停止。

## 2. 从 SanDisk 启动安装

固件启动菜单选择 SanDisk 的 UEFI/OpenCore，再选 Install macOS Sequoia。完整系统在本地；Apple 仍声明安装器可能需要联网获取机型/固件信息，不能保证整个流程断网。AX201 安装环境联网尚未实测。

安装环境的终端可从安装盘 Sequoia-Setup/Show-Install-Target.command 查看只读目标映射。仅在指定 SSK 容器中擦除旧 Tahoe 的系统卷组，命名 Sequoia；不要擦除物理盘、整个容器、约273GB数据区或SanDisk。选择该空系统卷安装。重启时继续从 SanDisk OpenCore 进入 macOS Installer，最后进入 Sequoia。

## 3. Sequoia 内安装 Graphics 并启用加速

保持 SanDisk 插着。在其安装分区 Sequoia-Setup 下运行 Finish-Sequoia-USB.command；也可从 SEQ-BOOT/Sequoia-USB 运行。脚本仅接受 15.8.1/24H32 且根系统在批准的 SSK 区域，安装本地 Graphics 包，给 SSK EFI 添加 Sequoia Wi-Fi 并切换加速配置。如系统要求，先批准系统扩展。然后重启，固件菜单选择 SSK 的 OpenCore。

SanDisk 的 OpenCore 始终保留 -wex-noaccel，可作为恢复入口。若加速无法登录，改从 SanDisk OpenCore 进入 Sequoia；需要恢复 SSK 配置时，运行 Sequoia-USB/Set-SSD-USB-Profile.command noaccel。保留安装盘到桌面/Metal/睡眠稳定性验证完成。
'''
    (setup / 'INSTALL-STEPS.md').write_text(steps, encoding='utf-8')
    (base / 'START-HERE.md').write_text(steps, encoding='utf-8')
    files = [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(root.rglob('*')) if p.is_file()]
    meta = load(setup / 'installer-verified.json')
    manifest = {'files': files,
                'installerSource': str(base / 'Downloads' / 'InstallAssistant.pkg'),
                'installerSha256': meta['sha256']}
    (root / 'usb-deployment.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'privateDelivery': str(root), 'efiFiles': len(files),
                      'efiBytes': sum(f['bytes'] for f in files), 'nativeMacOSTested': False}))


if __name__ == '__main__':
    main()

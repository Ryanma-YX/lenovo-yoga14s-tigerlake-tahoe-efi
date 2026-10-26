"""Add a verified local Recovery host to the existing PRIVATE USB delivery.

No image downloading or disk writes. Use OpenCore's unchanged Apple RSA verifier.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
import shutil


def digest(path, algorithm='sha256'):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--recovery', type=Path, required=True)
    parser.add_argument('--macrecovery', type=Path, required=True)
    args = parser.parse_args()
    base = args.preparation.resolve()
    root = base / 'Prepared' / 'USB-Delivery'
    setup = root / 'Sequoia-USB'
    spec = importlib.util.spec_from_file_location('macrecovery', args.macrecovery)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image = args.recovery / 'BaseSystem.dmg'
    chunklist = args.recovery / 'BaseSystem.chunklist'
    with contextlib.redirect_stdout(io.StringIO()):
        chunks = list(module.verify_chunklist(str(chunklist)))
        module.verify_image(str(image), str(chunklist))
    # This qualified host contains pkgutil --expand-full and codesign. It does
    # not dictate the installed OS; the pinned local package supplies that app.
    if digest(image) != '591f07a9a4a58d855a2e53b86a5f5da854a250000a66a9382adaf106c20f839b':
        raise ValueError('Recovery host differs from the inspected 14.6.1 / 23G93 image')
    metadata = json.loads((setup / 'installer-verified.json').read_text(encoding='utf-8-sig'))
    package = base / 'Downloads' / 'InstallAssistant.pkg'
    if digest(package) != metadata['sha256']:
        raise ValueError('Original complete installer hash mismatch')
    metadata['transferMd5'] = digest(package, 'md5')
    (setup / 'installer-verified.plist').write_bytes(plistlib.dumps(metadata))
    plan = json.loads((setup / 'disk-plan.json').read_text(encoding='utf-8-sig'))
    (setup / 'disk-plan.plist').write_bytes(plistlib.dumps(plan))
    recovery = root / 'com.apple.recovery.boot'
    recovery.mkdir(exist_ok=True)
    shutil.copy2(image, recovery / image.name)
    shutil.copy2(chunklist, recovery / chunklist.name)
    for name in ('recovery_disk_guard.sh', 'Recovery-Install.command'):
        shutil.copy2(Path(__file__).with_name(name), setup / name)
    # Retire the launcher that depends on the unstable old desktop. A stale
    # shortcut must stop before invoking its former formatting workflow.
    (setup / 'Start-USB.command').write_text(
        '#!/bin/bash\necho "Use the independent USB Recovery. See INSTALL-STEPS.md."\nexit 1\n', encoding='utf-8', newline='\n')
    instructions = '''# 从 U 盘独立 Recovery 全新安装 Sequoia

不再进入旧 Tahoe，也不要运行旧 Start-USB.command。SSK 的约 239GB 原 Tahoe 区域是唯一替换目标；约 273GB 数据分区和内部 Windows 盘保留。

1. 保持 SSK 和 SanDisk 插着，固件启动菜单选择 SanDisk UEFI/OpenCore，再选择外部的 macOS Base System（dmg）。这是 Sonoma 14.6.1 的独立恢复环境，只作为安装工具宿主；不要点它自带的“重新安装 macOS Sonoma”。本地完整安装包是 Sequoia 15.8.1 / 24H32。
2. 菜单“实用工具 → 终端”，执行：

```bash
diskutil mount USB_ESP_GUID
bash /Volumes/SEQ-BOOT/Sequoia-USB/Recovery-Install.command --show-target
```

记录它输出的 Replacement container 和 PROTECTED data partition。打开磁盘工具、显示所有设备，只在指定替换容器内选中旧 Tahoe 系统卷，使用“抹掉卷宗组”，命名 Sequoia、格式 APFS。不要抹整个 SSK、整个 APFS 容器、受保护的数据分区或 SanDisk。

3. 回到终端，执行：

```bash
bash /Volumes/SEQ-BOOT/Sequoia-USB/Recovery-Install.command
```

脚本重新核对 GPT、物理容量、分区边界和目标 APFS 容器；只接受该容器里名为 Sequoia 的新空卷。校验本地包、验证 Apple 原生签名、展开匹配安装 app、校验代码签名后打开 Sequoia 安装窗口。选择刚才的 Sequoia 卷。展开可能较慢，两只设备一直插着。失败时保留终端错误，不要绕过检查。日志保存在 Sequoia 卷的 macOS-Installer-* 目录。

4. 重启仍从 SanDisk OpenCore 进入，先选目标 SSD 的 macOS Installer，最后进入 Sequoia。完整系统包在本地；Apple 安装器仍可能要求联网验证，恢复环境的 AX201 网络尚未实测。
5. 进入 Sequoia 后执行：

```bash
sudo diskutil mount USB_ESP_GUID
bash /Volumes/SEQ-BOOT/Sequoia-USB/Finish-Sequoia-USB.command
```

若提示，先批准系统扩展，再重启从 SSK OpenCore 测试加速。SanDisk 保留 -wex-noaccel 恢复入口。需要恢复 SSK 无加速配置时，在 Sequoia 或完整 macOS 中运行 Set-SSD-USB-Profile.command noaccel（该后处理依赖完整系统的 osascript）。

本次完成 Windows 文件准备和读回校验；独立 Recovery 启动、原生 pkgutil/codesign、Sequoia 安装和 Metal 实测仍待现场执行。不要把静态或模拟测试当作安装成功。
'''.replace('USB_ESP_GUID', plan['usb']['esp']['guid'])
    (setup / 'INSTALL-STEPS.md').write_text(instructions, encoding='utf-8')
    (base / 'START-HERE.md').write_text(instructions, encoding='utf-8')
    report = dict(recoveryHost='Sonoma 14.6.1 / 23G93', installedOS='Sequoia 15.8.1 / 24H32',
        appleChunklistRsaVerified=True, allChunksVerified=len(chunks), recoverySha256=digest(image),
        nativeBootTested=False, installerExecuted=False, metalValidated=False)
    (setup / 'recovery-verified.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    files = [dict(path=p.relative_to(root).as_posix(), bytes=p.stat().st_size, sha256=digest(p))
        for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ('recovery-deployment.json', 'usb-deployment.json')]
    (root / 'recovery-deployment.json').write_text(json.dumps(dict(files=files), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(report, files=len(files))))


if __name__ == '__main__':
    main()

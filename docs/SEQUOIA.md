# Sequoia 15.8.1 安装准备

2026-10-26：从已确认的 Tahoe/触控板基线准备 Sequoia 对照系统。**没有把本机标为 Sequoia 启动或 Metal 成功。** 编译器移植研究保留在独立实验分支，暂不继续。

## 已选路线

机主选择最终不保留 Tahoe，只使用其所在的原约 239GB 区域；原约 273GB APFS 数据分区和内部 Windows 分区不作分区、格式化或安装操作。网络只有 AX201 Wi-Fi。后续已提供 64GB SanDisk U 盘，并明确授权清空整只 U 盘；当前改用独立 USB 安装介质。

采用完整本地安装器。保留 SanDisk 现有分区边界，在 Windows 格式化两个已授权分区：8GiB EFI 放完整 OpenCore 与准备工具，其余 NTFS 分区放完整 InstallAssistant.pkg。进入 Tahoe 后将安装 app 展开到本地，再只把 SanDisk 数据分区格式化为 HFS 并运行 Apple createinstallmedia。SSK 不缩容，准备期间其启动配置不变；从 SanDisk OpenCore 安装 Sequoia 后，再安装 Graphics 并给 SSK 配置启用加速。SanDisk 保持无加速恢复入口。旧的无额外介质/32GiB 缩容脚本保留供历史复现，当前不执行。

完整包无需在安装环境重新下载，但不能保证全流程断网：Apple 声明安装器仍可能联网获取机型/固件信息，AX201 在安装环境中的实际联网情况待验证。

机主明确选择不要保留 Tahoe 系统镜像，完整系统镜像的保留计划已取消。后续只要求经解压哈希复核的 ESP/GPT 小备份，不依赖旧 Tahoe 系统镜像。带真实身份的 EFI、磁盘计划和原始报告仅放在本地私有准备目录，不加入 Git。

## 版本与来源

| 组件 | 准备版本与处理 |
| --- | --- |
| macOS | Sequoia 15.8.1 / 24H32，Apple public-release catalog 产品 142-27431 |
| OpenCore | 保留 1.0.8 RELEASE |
| WEX / Graphics | 保留 0.5.0 / 0.2.0；在 Sequoia 内安装对应 payload |
| Wi-Fi | laobamac AirportItlwm Sequoia 2.4.0 alpha 738d4c6，Darwin 24.0.0–24.99.99 |
| 原 Tahoe Wi-Fi | 保留现有 Darwin 25 起的条目，以便制作安装器 |
| 声音 | 保留 AppleALC；SimpleHDA 保持 Darwin 25 限制，不加载到 Sequoia |
| 触控板、ACPI、Booter、SMBIOS | 在本机私有 EFI 副本中保留；不改动已验证的设置 |
| 安装前启动参数 | 保留 `-wex-noaccel`；安装 Graphics 成功后再使用准备好的加速配置 |

[Graphics 0.2.0 要求](https://github.com/b00t0x/WhateverXe-Graphics/blob/v0.2.0/README.md#requirements) 包含 Sequoia 15.8.x，目标构建含 24H32；无需退回旧驱动版本。[Wi-Fi release](https://github.com/laobamac/itlwm/releases/tag/v2.4.0-alpha) 是开发版本，是否可用仍需实机验证。

完整 InstallAssistant.pkg：15,664,523,626 字节，当前文件 SHA-256 为 `e4532e3337431292a7f227fcde7eb57f7b907547e2a26b43d3aab5a3f6e44781`。其 integrityDataV1 的 1,494 个 SHA-256 分块及清单自校验全部匹配。

**校验边界：** catalog 的 Digest 对应 XAR 压缩目录的 SHA-1，不是整包 SHA-1；目录摘要及包内保存的摘要已一致通过。完整数据另按 integrityDataV1 分块验证。该清单为方法 2（清单校验和），不是 macOS 原生签名验证。macOS 准备脚本还必须通过 `pkgutil --check-signature` 和安装器 app 的 codesign 检查，随后才允许缩放目标区域。

## 工具

目录 [tools/sequoia](../tools/sequoia/) 中：

- `download_installer.py`：Apple HTTPS 完整包断点下载、catalog 的 XAR 目录摘要及全包 SHA-256 分块校验。
- `Backup-ExternalSSD.ps1` / `backup_ranges.py`：按设备和分区身份匹配，默认只读备份 GPT 和 ESP；zstd 压缩后完整解压，核对长度和 SHA-256。完整系统镜像须显式指定 `-IncludeSystemImage`，本次后续不使用该选项。需要本机 Python 3.14 的 `compression.zstd`。
- `prepare_efi.py`：从本机真实 EFI 生成独立副本，只增加 Darwin 24 Wi-Fi 条目和文件；输出无加速/加速两种配置，运行 ocvalidate。
- `mac_disk_guard.js`：使用 macOS 自带 JXA，以已保存的三个 GPT 分区 UUID 的唯一组合识别 SSK，核对外接属性、磁盘容量、分区起点/大小及 APFS 物理存储。Windows 存储序列号不一定等于 macOS USB 桥序列号；缺失时不再作为唯一识别依据，若实际发现序列号冲突则停止。使用原生 `PartitionMapPartitionOffset`/`CapacityFree` 字段，并兼容旧 fixture 字段。外部介质模式还独立检查 USB 的 EFI UUID、容量与两个分区位置，不按固定磁盘编号操作。
- `build_usb_delivery.py` / `Deploy-USB.ps1`：生成含真实身份的本地私有 USB 包；校验全部来源文件与完整安装包后，只格式化符合已授权 USB 序列号、容量、分区 GUID/位置/大小的两个分区并写入，逐文件复核哈希。完整私有包不加入 Git。
- `Start-USB.command` / `Prepare-USB.command`：在现有 Tahoe 从 USB EFI 后台启动；本地签名、安装 app 校验通过后，只擦除独立 USB 的数据卷并制作完整介质。
- `Show-USB-Install-Target.command` / `Finish-Sequoia-USB.command` / `Set-SSD-USB-Profile.command`：不缩容路线的安装目标映射、Graphics 安装及 SSK 加速/无加速配置切换。USB 配置始终保留无加速。
- `Prepare-Installer.command`：从当前 Tahoe 校验、准备完整安装器和临时安装分区；保留现有 Tahoe，随后添加 EFI 的 Sequoia Wi-Fi 支持。读取 Windows NTFS 上已下载的安装包；若无法读取，则使用当前 Tahoe Wi-Fi 下载同一 Apple 包。
- `Show-Install-Target.command`：安装环境中的只读目标映射。通过 Disk Utility 擦除旧 Tahoe 的系统卷组这一步仍由机主在现场执行。
- `Finish-Sequoia.command`：只在 15.8.1/24H32 的批准目标上安装 Graphics，并切换到准备好的加速配置。
- `Restore-NoAccel.command`：在已识别的同一外接 SSD 上恢复无加速配置；可从安装环境使用，不卸载驱动或擦盘。

旧 `Prepared/Delivery/EFI/` 是**供脚本使用的增量文件**，不可据此替换整个原 EFI。新的 `Prepared/USB-Delivery/EFI/` 包含完整 Boot/OC，可从 SanDisk 独立启动；其 `Sequoia-USB/EFI/` 仍只是给 SSK 配置切换脚本使用的增量文件。

## 验证边界

Windows 已执行：完整安装器分块校验、Wi-Fi release 哈希校验、真实 EFI 的三份 ocvalidate、原 EFI 哈希检查、备份逻辑的模拟文件/解压恢复检查、JavaScript 安全边界 fixtures、Python 包校验 fixtures、Bash/PowerShell 语法检查。

macOS JXA 实际 plist 解析、USB eraseVolume/createinstallmedia、Sequoia 安装、扩展批准、Metal/GPU 读回、登录与桌面稳定性均必须单独实测。原脚本在本机序列号关联处失败并停止；新的 GPT 识别与 USB 原生制作路径尚未执行，若返回字段或运行环境不符合假设，应保留错误并停止。

需要现场完成的动作：切回 Tahoe 运行准备脚本、选择 OpenCore 安装项、按只读映射擦除旧系统卷组和选择安装目标、必要时批准扩展。当前 Windows 会话不能把跨系统重启与这些安装界面操作标成已经自动完成。

参考：[Apple 完整安装器](https://support.apple.com/en-us/102662)、[createinstallmedia](https://support.apple.com/en-us/101578)、[Apple chunklist 格式](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.101.4/bsd/kern/chunklist.h)、[Asahi 安装器的 diskutil 字段处理](https://github.com/AsahiLinux/asahi-installer/blob/main/src/diskutil.py)。

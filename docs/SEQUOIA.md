# Sequoia 15.8.1 安装准备

2026-10-26：从已确认的 Tahoe/触控板基线准备 Sequoia 对照系统。**没有把本机标为 Sequoia 启动或 Metal 成功。** 编译器移植研究保留在独立实验分支，暂不继续。

## 已选路线

机主选择最终不保留 Tahoe，只使用其所在的原约 239GB 区域；原约 273GB APFS 数据分区和内部 Windows 分区不作分区、格式化或安装操作。没有额外安装介质，网络只有 AX201 Wi-Fi。

采用完整离线安装器。准备时先保留当前 Tahoe，在其物理存储区域尾部临时腾出约 32GiB HFS 安装分区，用 Apple 的 createinstallmedia 制作介质；待从该介质成功启动，才擦除旧 Tahoe 的**系统卷组**并安装 Sequoia。临时介质保留到实机验证后再考虑回收，不在 Windows 中直接缩放 APFS。

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
- `mac_disk_guard.js`：使用 macOS 自带 JXA，关联 USB 序列号与 IOMedia，核对磁盘容量、分区 UUID/起点/大小及 APFS 物理存储。标识不匹配便停止，不按固定磁盘编号操作。
- `Prepare-Installer.command`：从当前 Tahoe 校验、准备完整安装器和临时安装分区；保留现有 Tahoe，随后添加 EFI 的 Sequoia Wi-Fi 支持。读取 Windows NTFS 上已下载的安装包；若无法读取，则使用当前 Tahoe Wi-Fi 下载同一 Apple 包。
- `Show-Install-Target.command`：安装环境中的只读目标映射。通过 Disk Utility 擦除旧 Tahoe 的系统卷组这一步仍由机主在现场执行。
- `Finish-Sequoia.command`：只在 15.8.1/24H32 的批准目标上安装 Graphics，并切换到准备好的加速配置。
- `Restore-NoAccel.command`：在已识别的同一外接 SSD 上恢复无加速配置；可从安装环境使用，不卸载驱动或擦盘。

含本机身份的交付目录中 `EFI/` 是**供脚本使用的增量文件**，不是可单独启动的完整 EFI；不可据此删除或替换整个原 EFI 目录。

## 验证边界

Windows 已执行：完整安装器分块校验、Wi-Fi release 哈希校验、真实 EFI 的三份 ocvalidate、原 EFI 哈希检查、备份逻辑的模拟文件/解压恢复检查、JavaScript 安全边界 fixtures、Python 包校验 fixtures、Bash/PowerShell 语法检查。

macOS JXA 实际 plist 解析、live resize、createinstallmedia、Sequoia 安装、扩展批准、Metal/GPU 读回、登录与桌面稳定性均必须单独实测。新脚本在 macOS 尚未执行；若本机返回字段或运行环境不符合假设，应保留错误并停止，不能删去守卫条件“强行继续”。

需要现场完成的动作：切回 Tahoe 运行准备脚本、选择 OpenCore 安装项、按只读映射擦除旧系统卷组和选择安装目标、必要时批准扩展。当前 Windows 会话不能把跨系统重启与这些安装界面操作标成已经自动完成。

参考：[Apple 完整安装器](https://support.apple.com/en-us/102662)、[createinstallmedia](https://support.apple.com/en-us/101578)、[Apple chunklist 格式](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.101.4/bsd/kern/chunklist.h)。

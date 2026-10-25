# Lenovo Yoga 14s · Tiger Lake · Tahoe EFI

> 从 `EXITBS:START` 走到 macOS 安装界面的一份实机 EFI 与排查笔记。

本仓库归档联想 Yoga 14s 2021（82G2）、i5-1135G7、Iris Xe `8086:9A49` 的 OpenCore 配置。2026-10-25，机主确认这版 EFI 已能进入 macOS 恢复/安装界面。

**当前里程碑是进入安装界面，不是完整安装成功，也不是已验证 Metal 加速。**

仓库中的 EFI 已脱敏：机器序列号、MLB、SystemUUID、ROM 与蓝牙控制器缓存没有上传。原本正在使用的 U 盘 EFI 没有因归档而修改。恢复镜像、Graphics 安装包、原始硬件报告和完整启动日志也不在仓库里。

## 实机与状态

| 项目 | 配置 / 验证情况 |
| --- | --- |
| 机型 | Lenovo Yoga 14s 2021 / 82G2 |
| BIOS | FJCN65WW，实机 OpenCore 日志报告 `MAT support is 0` |
| CPU | i5-1135G7，4 核 8 线程，Tiger Lake-UP3 |
| 内存 | 16GB |
| 核显 | Intel Iris Xe，`8086:9A49` |
| 内屏 | 2880×1800；完整分辨率、背光行为待验证 |
| 无线 | Intel AX201；实际联网稳定性待验证 |
| 音频 | ALC287；音频、麦克风待验证 |
| SMBIOS | `MacBookPro16,2` |
| 引导器 | OpenCore 1.0.8 **DEBUG** |
| 恢复环境 | Tahoe 26.6.2 / 25G83；日志内核版本 25.6.0 |
| 已确认 | UEFI U 盘引导、加载恢复镜像、进入安装界面 |
| 尚未确认 | 完整安装、系统桌面、Metal、USB 全端口、睡眠、触控板及各外设 |

## 最终保留的关键设置

| 路径 | 值 | 依据 |
| --- | --- | --- |
| `Kernel/Emulate/Cpuid1Data` | `E5060700 00000000 00000000 00000000` | Ice Lake CPU 伪装 |
| `Kernel/Emulate/Cpuid1Mask` | `FFFFFFFF 00000000 00000000 00000000` | 只覆盖签名字段 |
| `Kernel/Quirks/AppleXcpmCfgLock` | `true` | 实机报告 CFG Lock；处理 0xE2 相关访问 |
| `Kernel/Quirks/AppleXcpmExtraMsrs` | **`true`** | 同款 CPU、相同 CPUID 参考项目的明确要求；补上后机主反馈进入安装界面 |
| `Kernel/Quirks/ProvideCurrentCpuInfo` | `false` | 不对同构 Tiger Lake 强制应用非对称 SMP 拓扑补丁 |
| `Booter/Quirks/EnableWriteUnprotector` | `true` | 本机无 MAT 的配置组合 |
| `Booter/Quirks/RebuildAppleMemoryMap` | `false` | 与上述组合配套 |
| `Booter/Quirks/SyncRuntimePermissions` | `false` | 与上述组合配套 |
| `Booter/Quirks/DevirtualiseMmio` | `false` | 没有建立本机 MMIO 白名单 |
| `Booter/Quirks/SetupVirtualMap` | `true` | 最终成功进入安装界面的累计配置中保留；没有独立 A/B 证明它是根因 |
| `Misc/Security/SecureBootModel` | `Disabled` | 首次制作时即已关闭 |
| `Misc/Security/DmgLoading` | `Signed` | 使用 Apple 签名恢复镜像 |
| `Booter/Quirks/FixupAppleEfiImages` | `true` | 配合当前加载路径 |
| `Kernel/Quirks/XhciPortLimit` | `false` | 端口映射仍需实机完善 |
| `Misc/Debug/Target` | `65` | 保留文件日志，关闭 OpenCore 调试刷屏 |

默认启动参数：

```text
-v debug=0x100 keepsyms=1 -allow3d -disablegfxfirmware -vi2c-force-polling
```

29 个启用的 kext 条目、11 个 ACPI 表。Lilu 在依赖它的插件之前；VirtualSMC、USBToolBox 和 VoodooI2C 的声明依赖同样按序排列。完整版本见 [组件清单](docs/kext-inventory.json)。

## 来龙去脉

1. 最初目标是为 OpCore-Simplify 增加 Tiger Lake Xe-LP 识别，以及 WhateverXe / AMFIPass Mod 的选择、来源隔离和配置生成。
2. 根据本机硬件报告和 ACPI，制作 Tahoe 在线恢复 U 盘。恢复镜像通过 Apple chunklist 校验，但首次实机画面停在 `EXITBS:START`。
3. 实机历史 DEBUG 日志显示无 MAT，而最初生成器按芯片组使用了现代内存映射组合。改成无 MAT 组合后，仍未解决卡住。
4. 移除构建脚本额外强制开启的 `ProvideCurrentCpuInfo`；DEBUG 改为写文件，减少刷屏。日志到交接处的时间从约 187 秒缩短为约 54 秒，启动问题仍在。
5. 单独将 `SetupVirtualMap` 改为 `true`，作为兼容性试验。该变化没有独立实测结论。
6. 进一步联网核对同款 i5-1135G7 项目，发现遗漏了 `AppleXcpmExtraMsrs=true`。在保留其他设置的基础上开启这一项。
7. 机主随后确认可以进入安装界面。**这是累计配置的成功反馈，不能把所有因果都归给最后一个开关。**

更多细节见 [排查记录](docs/TROUBLESHOOTING.md)。

## 使用与恢复

1. 下载仓库，先阅读 [安装与个性化](docs/INSTALL.md)。
2. 将自己的 SMBIOS 身份填回副本。可用 `tools/personalize.py` 从自己的原始配置生成独立的 `build/EFI`；身份不会写回仓库模板。
3. 使用本仓库的检查脚本与同版本 ocvalidate 验证，再将生成的 `EFI` 目录放到目标启动分区根目录。
4. BIOS 采用 UEFI 引导并关闭固件 Secure Boot；这与 OpenCore 内的 `SecureBootModel` 是两项设置。
5. 进入 OpenCore，选择恢复镜像的 `(dmg)` 项。安装重启时，选择目标 SSD 上的 `macOS Installer` / 系统项继续。

本仓库不包含安装镜像。恢复镜像按 OpenCore 的 `macrecovery` 流程取得，将配套的 DMG 和 chunklist 放入启动分区根目录的 `com.apple.recovery.boot`。

`profiles/config-basic-display.plist` 与主配置只相差 `-wexoff`，用于关闭 WhateverXe 的基础显示排查；它不是另一个已经验证成功的整套硬件配置。

## Xe 图形加速的边界

已包含 WhateverXe 0.5.0 和专用 AMFIPass 1.4.1 Mod，SIP Data 为 `03080000`。没有同时启用 WhateverGreen，也没有传统 iGPU `ig-platform-id/device-id` 伪装。

按本次归档时的 [WhateverXe 0.5.0 说明](https://github.com/b00t0x/WhateverXe/blob/0.5.0/README.md)，Graphics 0.2.0 的 Tahoe 条件为 **26.7 或更新版本**。本次恢复环境是 26.6.2；进入安装界面不表示满足了图形加速条件。Graphics pkg 需要在安装后的 macOS 内按其要求部署，不属于 EFI 文件。

USB 当前采用 `USBToolBox + UTBDefault`，仍是映射前的通用组合，不宣称已经完成本机 USB 定制。

## 检查

在 Windows 上安装 Python 3 后：

```powershell
python tools/validate_efi.py
```

包含 plist 重复键、文件引用、ACPI 校验和、活动 kext 标识唯一性与依赖顺序、x86_64 EFI 架构、脱敏字段、SHA-256，以及 OpenCore 1.0.8 `ocvalidate.exe` 的检查。结果保存在 [验证记录](docs/validation.json)。这些静态检查不能代替实机启动。

## 来源与致谢

- [OpenCorePkg](https://github.com/acidanthera/OpenCorePkg) 与 Acidanthera 驱动项目
- [OpCore-Simplify](https://github.com/lzhoang2801/OpCore-Simplify)：生成器基线；本地 Xe 扩展补丁在 `patches/`，本机最终修正以本仓库 EFI 为准
- [WhateverXe](https://github.com/b00t0x/WhateverXe) / [WhateverXe Graphics](https://github.com/b00t0x/WhateverXe-Graphics)
- [同款 CPU 的 Samsung 参考](https://github.com/lshbluesky/Samsung-NT750XDA-KF59U-Hackintosh#-install-guide)：明确记录 ExtraMsrs 与 EXITBS 的关联；该参考主要覆盖到 Sonoma，不等于本机 Tahoe 的直接证明
- [同款 CPU 的 Lenovo 参考](https://github.com/keserbaros1/Hackintosh-Lenovo-Ideapad-5-14ITL05-i5-1135G7-EFI-Tigerlake)
- laobamac、OpenIntelWireless、USBToolBox、VoodooI2C、YogaSMC、RehabMan 及各组件作者

组件下载地址和包校验和见 [来源清单](docs/component-sources.json)，第三方权利说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。这是配置归档，不是上述项目的官方发行版。

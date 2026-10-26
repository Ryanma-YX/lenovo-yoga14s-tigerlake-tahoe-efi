# Lenovo Yoga 14s · Tiger Lake · Tahoe EFI

> 从 `EXITBS:START` 到安装完成、SSD 独立启动及触控板可用的实机 EFI 与排查笔记。

本仓库归档联想 Yoga 14s 2021（82G2）、i5-1135G7、Iris Xe `8086:9A49` 的 OpenCore 配置。2026-10-26，已安装 macOS Tahoe 26.7.1，能通过外接 SSD 自带的 EFI 启动；机主确认定向 ACPI 修复后触控板正常。

**触控板已实机确认可用；Metal 和桌面稳定性仍有问题。这不是一套已经完善的日用配置。** 主配置保留 `-wex-noaccel`，暂时禁用 GPU 加速；该模式下仍出现过 WindowServer 卡死。见 [显卡故障与后续方案](docs/GRAPHICS.md)。

编译器替换研究现有独立 [诊断实验](experiments/xe-compiler/README.md)：已完成 ABI/依赖静态审查和 CPU mock 测试，提供原 adapter 的 LLDB 输入捕获、离线重放及 macOS 操作说明。尚无真实失败 shader、macOS 构建或替代驱动实机结论；没有改动本 EFI。

仓库中的 EFI 从当前 SSD 实际启动文件同步，机器序列号、MLB、SystemUUID、ROM 与蓝牙控制器缓存已脱敏。恢复镜像、Graphics 安装包、原始硬件报告和完整启动日志不在仓库里。最初的 DEBUG 安装介质版本保留在 Git 历史中。

## 实机与状态

| 项目 | 配置 / 验证情况 |
| --- | --- |
| 机型 | Lenovo Yoga 14s 2021 / 82G2 |
| BIOS | FJCN65WW，实机 OpenCore 日志报告 `MAT support is 0` |
| CPU | i5-1135G7，4 核 8 线程，Tiger Lake-UP3 |
| 内存 | 16GB |
| 核显 | Intel Iris Xe，`8086:9A49` |
| 内屏 | 2880×1800；正常启动日志记录该模式，背光行为待验证 |
| 无线 | Intel AX201；实际联网稳定性待验证 |
| 音频 | ALC287；音频、麦克风待验证 |
| SMBIOS | `MacBookPro16,2` |
| 引导器 | OpenCore 1.0.8 **RELEASE**，OpenCore 调试文件输出已关闭 |
| 已装系统 | Tahoe 26.7.1 / 25G241；Darwin 25.6.0 |
| 触控板 | ELAN HID-over-I2C，I2C1.TPD0；定向补丁后机主确认正常 |
| DVMT | 当前物理预分配 64MiB，未改 BIOS 为 96MiB |
| 已确认 | 安装完成、进入桌面、外接 SSD 独立启动、触控板可用 |
| 未解决 / 待验证 | Metal 编译失败、WindowServer 卡死、USB 全端口、睡眠及各外设 |

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
| `Misc/Debug/Target` | `0` | 已切换 RELEASE，关闭 OpenCore 调试输出；内核诊断启动参数仍保留 |
| `ACPI/Add/SSDT-YTPD.aml` | `true` | 修复本机触控板发布与 ELAN 初始化；两个 DSDT 方法定向改名配套使用 |

默认启动参数：

```text
-v debug=0x100 keepsyms=1 -allow3d -disablegfxfirmware -vi2c-force-polling -wex-noaccel
```

29 个启用的 kext 条目、12 个 ACPI 表。Lilu 在依赖它的插件之前；VirtualSMC、USBToolBox 和 VoodooI2C 的声明依赖同样按序排列。触控板保留轮询模式，不宣称 GPIO 中断模式已验证。完整版本见 [组件清单](docs/kext-inventory.json)。

## 来龙去脉

1. 最初目标是为 OpCore-Simplify 增加 Tiger Lake Xe-LP 识别，以及 WhateverXe / AMFIPass Mod 的选择、来源隔离和配置生成。
2. 根据本机硬件报告和 ACPI，制作 Tahoe 在线恢复 U 盘。恢复镜像通过 Apple chunklist 校验，但首次实机画面停在 `EXITBS:START`。
3. 实机历史 DEBUG 日志显示无 MAT，而最初生成器按芯片组使用了现代内存映射组合。改成无 MAT 组合后，仍未解决卡住。
4. 移除构建脚本额外强制开启的 `ProvideCurrentCpuInfo`；DEBUG 改为写文件，减少刷屏。日志到交接处的时间从约 187 秒缩短为约 54 秒，启动问题仍在。
5. 单独将 `SetupVirtualMap` 改为 `true`，作为兼容性试验。该变化没有独立实测结论。
6. 进一步联网核对同款 i5-1135G7 项目，发现遗漏了 `AppleXcpmExtraMsrs=true`。在保留其他设置的基础上开启这一项。
7. 机主随后确认可以进入安装界面。**这是累计配置的成功反馈，不能把所有因果都归给最后一个开关。**
8. 完成 Tahoe 26.7.1 安装，将 EFI 迁移到外接 SSD，并换成匹配的一套 OpenCore 1.0.8 RELEASE 文件，不再依赖另插安装 U 盘。
9. 安装 WhateverXe Graphics 0.2.0 并允许扩展后出现登录黑屏。11 份 WindowServer 报告均指向编译适配器拒绝 bitcode。安全模式能进入桌面；随后使用 `-wex-noaccel` 能正常登录，但仍有 WATCHDOG 卡死。
10. 正常启动日志显示 I2C 控制器已加载、触控板 TPD0 未枚举。新增本机限定的 `SSDT-YTPD`，保留原资源方法并修正 macOS 下的设备状态与 ELAN 参数，机主确认触控板正常。

更多细节见 [排查记录](docs/TROUBLESHOOTING.md)。

## 使用与恢复

1. 下载仓库，先阅读 [安装与个性化](docs/INSTALL.md)。
2. 将自己的 SMBIOS 身份填回副本。可用 `tools/personalize.py` 从自己的原始配置生成独立的 `build/EFI`；身份不会写回仓库模板。
3. 使用本仓库的检查脚本与同版本 ocvalidate 验证，再将生成的 `EFI` 目录放到目标启动分区根目录。
4. BIOS 采用 UEFI 引导并关闭固件 Secure Boot；这与 OpenCore 内的 `SecureBootModel` 是两项设置。
5. 进入 OpenCore，选择恢复镜像的 `(dmg)` 项。安装重启时，选择目标 SSD 上的 `macOS Installer` / 系统项继续。

本仓库不包含安装镜像。恢复镜像按 OpenCore 的 `macrecovery` 流程取得，将配套的 DMG 和 chunklist 放入启动分区根目录的 `com.apple.recovery.boot`。

`profiles/config-basic-display.plist` 与主配置只相差 `-wexoff`，用于关闭 WhateverXe 的基础显示排查；它不是另一个已经验证成功的整套硬件配置。

触控板源码和回退方法见 [触控板修复](docs/TOUCHPAD.md)。本机 BIOS 型号、表长度与唯一字节模式均有限定，不应把此补丁直接套在其他机器上。

## Xe 图形加速的边界

已包含 WhateverXe 0.5.0 和专用 AMFIPass 1.4.1 Mod，SIP Data 为 `03080000`。没有同时启用 WhateverGreen，也没有传统 iGPU `ig-platform-id/device-id` 伪装。

按 [WhateverXe 0.5.0 说明](https://github.com/b00t0x/WhateverXe/blob/0.5.0/README.md)，Graphics 0.2.0 的 Tahoe 条件为 **26.7 或更新版本**。当前系统 26.7.1 已满足该版本条件，但实机仍出现 shader 编译失败；版本满足不等于功能已经正常。Graphics pkg 安装在 macOS 的 `/Library` 下，不属于 EFI 文件，单纯换 EFI 不能重建编译适配器。

当前保留 `-wex-noaccel` 作为诊断退路，尚未恢复可稳定使用的 Metal。DVMT 64MiB 是已读出的实际值；增加到上游建议的 96MiB 可以作为 BIOS 提供选项时的对照，但没有证据表明它能解决本次 bitcode 拒绝。

USB 当前采用 `USBToolBox + UTBDefault`，仍是映射前的通用组合，不宣称已经完成本机 USB 定制。

## 检查

在 Windows 上安装 Python 3 后：

```powershell
python tools/validate_efi.py
```

包含 plist 重复键、文件引用、ACPI 校验和、活动 kext 标识唯一性与依赖顺序、x86_64 EFI 架构、脱敏字段、SHA-256，以及 OpenCore 1.0.8 `ocvalidate.exe` 的检查。结果保存在 [验证记录](docs/validation.json)。触控板另做了本机 AML 解释器验证及机主实机确认；这些记录不代表显卡或整机稳定性通过。

## 来源与致谢

- [OpenCorePkg](https://github.com/acidanthera/OpenCorePkg) 与 Acidanthera 驱动项目
- [OpCore-Simplify](https://github.com/lzhoang2801/OpCore-Simplify)：生成器基线；本地 Xe 扩展补丁在 `patches/`，本机最终修正以本仓库 EFI 为准
- [WhateverXe](https://github.com/b00t0x/WhateverXe) / [WhateverXe Graphics](https://github.com/b00t0x/WhateverXe-Graphics)
- [同款 CPU 的 Samsung 参考](https://github.com/lshbluesky/Samsung-NT750XDA-KF59U-Hackintosh#-install-guide)：明确记录 ExtraMsrs 与 EXITBS 的关联；该参考主要覆盖到 Sonoma，不等于本机 Tahoe 的直接证明
- [同款 CPU 的 Lenovo 参考](https://github.com/keserbaros1/Hackintosh-Lenovo-Ideapad-5-14ITL05-i5-1135G7-EFI-Tigerlake)
- laobamac、OpenIntelWireless、USBToolBox、VoodooI2C、YogaSMC、RehabMan 及各组件作者

组件下载地址和包校验和见 [来源清单](docs/component-sources.json)，第三方权利说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。这是配置归档，不是上述项目的官方发行版。

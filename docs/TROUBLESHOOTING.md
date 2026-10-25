# EXITBS 排查记录

## 证据与结论分开

| 阶段 | 可观察结果 | 能得出的结论 |
| --- | --- | --- |
| 初次 RELEASE EFI | 恢复镜像内的内核集合读取成功，最后可见 EXITBS | 引导载荷已经读取；末行不能唯一定位死锁原因 |
| 无 MAT 组合 | DEBUG 日志确认 WRUNPROT=1、RBMAP=0、RTPERMS=0、MAT=0 | 内存映射修正确实生效，但单独不足以解决问题 |
| 关闭强制 CPU 拓扑补丁 | 不再应用强制 core/thread 拓扑修改 | 排除一项不必要的覆盖，仍未进入界面 |
| 关闭 OpenCore 屏幕调试输出 | 到 EXITBS 从约 187 秒降至约 54 秒 | 日志刷屏影响速度，不能将提速视为修复 |
| SetupVirtualMap=true | 成为后续累计配置的一部分 | 没有单独 A/B 证明其必要性 |
| ExtraMsrs=true | 机主随后反馈进入安装界面 | 最终配置达到恢复/安装界面里程碑；最后改动有同款 CPU 项目依据 |

没有在每一个组合上做严格、重复的单变量实验，因此不声称最后一个开关单独解释了全部问题。

## 三行 ERR 是什么

当时可见：

```text
EB.LD.OFS|OPEN! ... usr\standalone\OS.dmg.root_hash ... Err(0xE)
EB.RH.LRH|P! ... EB.LD.LF
EB.BST.FBS|! ... EB.RH.LRH
```

后两行是同一个错误沿调用链返回，不是三个文件分别打开失败。日志此前已有 `Prelinked status - Success`、`EB.LD.LKFS Ok(0)` 和 `EB.LD.LKC Ok(0)`。

这些行不能直接等同于镜像损坏、缺失 U 盘 chunklist 或 USB 掉线。制作时，DMG / chunklist 齐全且通过 Apple 校验；但这也不是对所有后续运行时问题的排除证明。

## 哪些网络方案没有直接照搬

- **SecureBootModel=Disabled**：本机首次制作时已经如此，因此不是后面才发现的漏项。
- **DmgLoading=Any**：实际 Apple 签名镜像已经加载，保留 Signed。
- **AppleMCEReporterDisabler**：未见明确 MCE panic，当前 SMBIOS 是 MacBookPro16,2；没有因其他机器的成功帖子而添加它。
- **随意重排 plist**：字典字段位置不决定加载顺序；Kernel/Add 数组依赖顺序才重要。实际依赖检查没有倒序或活动 bundle 重复。
- **U 盘不能启动**：实际从 USB 上加载了 OpenCore、DMG、boot.efi 与内核集合。但 macOS 接管后的 USB 映射仍需验证。
- **XhciPortLimit 在所有新系统必定失效**：该说法过时；OpenCore 后续有兼容性更新。本机仍保留 false，优先完成真正的端口映射。

## 后续实机进展（2026-10-26）

完成 Tahoe 26.7.1 / 25G241 安装，外接 SSD 独立引导通过，OpenCore 已切换 1.0.8 RELEASE。安装 Graphics 0.2.0 后出现登录黑屏：11 份 WindowServer 报告为 COREANIMATION code 4，适配器报 `Xe compiler unsupported bitcode layout`。禁用加速后可登录，但另有主线程无响应 40 秒的 WATCHDOG 报告，不能视为同一个错误或完整修复。

触控板最初已有启用的 VoodooI2C/VoodooI2CHID，正常启动时控制器已加载，但 ACPI 中没有 TPD0 设备。定向覆盖本机 TPD0 的状态与 ELAN 初始化后，机主确认触控板正常。详见 [触控板修复](TOUCHPAD.md) 与 [显卡故障](GRAPHICS.md)。

## 验证清单

- [x] 完成 macOS 安装，进入桌面并记录准确系统构建：26.7.1 / 25G241。
- [ ] 完成本机 USB 端口映射，替换 UTBDefault。
- [x] 机主确认触控板可用；GPIO 中断模式仍未验证。
- [ ] 完成键盘各键、无线、蓝牙、音频与麦克风验证。
- [ ] 验证高分屏、背光、外接显示与睡眠。
- [x] 在满足系统版本条件后安装 Graphics 0.2.0；Metal 验证失败，继续排查。
- [ ] 修复 shader 编译问题及禁用加速后的 WindowServer 卡死。
- [x] 验证外置 SSD 上的独立 OpenCore 引导。
- [x] 切换匹配的 OpenCore RELEASE 文件，关闭 OpenCore 调试输出。
- [ ] 稳定后减少剩余内核诊断参数。

## 参考

- [同款 i5-1135G7 安装要求](https://github.com/lshbluesky/Samsung-NT750XDA-KF59U-Hackintosh#-install-guide)
- [联想同款 CPU EFI](https://github.com/keserbaros1/Hackintosh-Lenovo-Ideapad-5-14ITL05-i5-1135G7-EFI-Tigerlake)
- [OpenCore 1.0.8 原始配置说明](https://github.com/acidanthera/OpenCorePkg/blob/1.0.8/Docs/Configuration.tex)
- [OpenCore 更新记录](https://github.com/acidanthera/OpenCorePkg/blob/1.0.8/Changelog.md)
- [USBToolBox：UTBDefault 与 UTBMap](https://github.com/USBToolBox/kext#usage)

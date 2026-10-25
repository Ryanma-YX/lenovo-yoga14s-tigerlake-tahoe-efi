# ELAN 触控板：已实机确认可用

2026-10-26，机主反馈应用本次补丁后触控板正常。没有额外声称所有手势、睡眠唤醒或 GPIO 中断模式均通过。

## 故障证据

Windows 将设备识别为 ELAN 子系统的 HID-over-I2C 触控板，兼容 ID 为 PNP0C50，路径为 `_SB.PC00.I2C1.TPD0`。原 EFI 中 VoodooI2CServices、VoodooGPIO、VoodooI2C、VoodooInput、VoodooI2CHID 都已启用，PS2 的重复 VoodooInput 已关闭。

正常启动的 macOS 日志显示 I2C1 控制器和 VoodooI2CControllerDriver 已 active，但 IOACPIPlane 中没有 TPD0，也没有 VoodooI2CHID 或触控板 HID 服务。因此修复点在设备枚举和初始化，而不是重复勾选 kext。

OEM `_STA` 要求 TPDT、TPVD 非零且 I2CN bit0 非零才返回 0x0F。日志没有给出这些对象的运行时值，所以不能事后认定其中哪一个字段一定是根因。

## 改动

源码在 [SSDT-YTPD.dsl](../ACPI-Sources/SSDT-YTPD.dsl)。配置新增两条 DSDT 定向改名，将本机 TPD0 的 `_STA`、`_INI` 分别改为 XSTA、XINI，再由新 SSDT 提供包装方法：

- macOS 下 `_STA` 返回 0x0F，允许设备发布。
- `_INI` 保留原 GPIO/pad 初始化，然后设置本机 ELAN 身份、I2C 地址 0x15、HID 描述符寄存器 1；有效的原总线速度保留。
- 原 `_CRS`、`_DSM` 继续使用 BADR、SPED、HID2，未整体替换资源模板。
- 其他系统调用原方法；不直接改写 TPDT/TPVD 等固件共享字段。
- 保留 `-vi2c-force-polling`，先验证基本输入。

地址和描述符寄存器来自本机固件中 ELAN0001 的分支，与 Windows 的子系统身份相符。补丁限定 DSDT OEM Table ID `CB-01`、长度 329812 字节及唯一模式；不是通用 ELAN 修复。

## 检查与回退

iASL 编译为 397 字节，0 错误、0 警告；OpenCore 1.0.8 ocvalidate 通过。两条字节模式在本机 DSDT 各匹配一次。

本地 ACPICA 使用本机 DSDT、OEM SSDT 和模拟 OperationRegion 解释执行：分别模拟原设备状态条件成立和不成立，核对 macOS 的状态、资源地址和 `_DSM` 描述符返回值；Windows 分支与基线结果一致。原表单独解释已有未解析节点/缓存诊断，补丁没有增加诊断；这不等于整套固件无错误。随后由机主完成实机确认。

若需回退，在配置中同时禁用 `SSDT-YTPD.aml` 和两条带有 `Yoga14s TPD0` 注释的 ACPI Patch。不能只禁用 SSDT 而保留改名，否则原 `_STA`/`_INI` 将缺失。使用自己的原始备份恢复整份 config.plist 也可以。

上游说明：[PNP0C50 与 VoodooI2CHID](https://github.com/VoodooI2C/VoodooI2C/blob/master/Documentation/Satellites.md)、[轮询模式与 GPIO 中断](https://github.com/VoodooI2C/VoodooI2C/blob/master/Documentation/Installation.md)。

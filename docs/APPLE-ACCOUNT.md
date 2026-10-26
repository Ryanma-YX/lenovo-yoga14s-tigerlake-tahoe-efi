# Apple Account、Sequoia 与内建网络接口

## Sequoia 的虚拟机变化

Apple 的 [Using iCloud with macOS virtual machines](https://developer.apple.com/documentation/virtualization/using-icloud-with-macos-virtual-machines) 明确说明：macOS 15 起，Apple silicon 上由 Virtualization 框架新建、使用 macOS 15 镜像的 VM 可使用由宿主 Secure Enclave 安全信息派生的独立身份访问 iCloud。把旧 VM 直接升级到 15 不会获得这项支持；迁移或克隆也会影响 VM 身份并要求重新认证。

这是官方虚拟机方案的身份机制，不能据此推导 Intel 黑苹果上的 Apple Account 全部被封，也不能把旧 VM 的未知错误直接归到本机的同一原因。本机验证码后的实际认证响应仍需另行捕获。

## OpenCore Configurator 的作用

[OpenCore Configurator 作者介绍](https://mackie100projects.altervista.org/opencore-configurator/) 将其定义为生成和编辑 OpenCore EFI 配置的图形界面。它可帮助修改填写错误的配置字段；没有证据证明安装这个应用本身能够绕过 Apple 的认证机制，或必然修复 Sequoia 的未知错误。

如果教程通过它更正了 SMBIOS、ROM、NVRAM 或设备属性，起作用的是被修正的配置及其适用条件。当前机器已有一套连续使用的身份，不应为了试验软件而反复生成新身份。任何编辑还应匹配当前 OpenCore 配置格式并用同版本 ocvalidate 检查。

## SSDT-RMNE + NullEthernet 是否有用

[NullEthernet 上游 README](https://github.com/RehabMan/OS-X-Null-Ethernet#readme) 的目的就是在缺少可用内建网络接口时提供假以太网设备，供 Mac App Store 等服务使用。SSDT-RMNE 提供 ACPI 设备，NullEthernet 驱动发布网络接口；它没有实际的有线联网能力，上网仍依赖真正的 Wi-Fi/USB 网络。

上游说明也明确优先采用有驱动的真实内建以太网或 PCIe AirPort，无此条件时才使用 NullEthernet。该方案是早期项目，原文已有 en0/IOBuiltIn 的验证，但并不是 Sequoia 登录问题的通用认证补丁。

本机使用 AirportItlwm，应先确认运行中的接口：

```bash
networksetup -listallhardwareports
ioreg -r -c IONetworkInterface -l -w0 | grep -E 'IOInterfaceName|IOBuiltin|IOPrimaryInterface'
```

需要把同一个接口的 `IOInterfaceName=en0` 与 `IOBuiltin=true`（某些显示形式为 Yes）对应起来查看，而不是只确认列表里存在 en0。如果原无线接口已经满足，不因“笔记本只有 Wi-Fi”再叠加假网卡。新版日志采集工具会保存完整接口记录供判断。

[Dortania 的 iServices 指南](https://dortania.github.io/OpenCore-Post-Install/universal/iservices.html#fixing-en0) 将内建 en0、ROM/SMBIOS 一致性与 NVRAM 列为排查项。这是配置排查指南，不是 Apple 对登录成功的保证。本轮尚未得到当前 Sequoia 网络接口的完整证据，因此没有加入 NullEthernet，也没有清除网络配置或改动机器身份。

## 本机已有证据

App Store 视频冻结的 GPU Reset 与 [Sequoia 实测](SEQUOIA-RESULTS.md) 对照已保存为脱敏结论。隔离 VA 后 App Store 可打开，不等同于账户已登录成功。旧日志中会话退出时的 Unknown error 124，以及 bag 配置请求超时，都不足以证明 Apple 账户被拒绝。

后续账户诊断应在当前稳定的 VA 隔离状态，记录一次尝试的准确时间和画面错误，先检查运行时内建接口及请求结果，再决定是否需要调整配置。

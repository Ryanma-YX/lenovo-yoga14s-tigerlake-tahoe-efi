# Iris Xe 9A49：显卡故障与下一步

检查日期：2026-10-26。当前配置可以启动，触控板正常，但不能宣称 Metal 和桌面稳定性已经修复。

## 两种故障分别处理

| 模式 | 实机证据 | 当前判断 |
| --- | --- | --- |
| 启用加速 | 最新本地采集目录重新解析得到 13 份唯一 WindowServer 报告（早先审查为 11 份），COREANIMATION code 4，`Xe compiler unsupported bitcode layout`，调用栈包含 `CA::OGL::MetalContext::create_pipeline_state` | Metal shader 编译链中的失败导致桌面进程退出 |
| `-wex-noaccel` | 可登录；02:37:54、02:39:14 的报告为 WATCHDOG code 1，主线程超过 40 秒未 checkin | 另有桌面卡死，不能称为同一个编译错误 |
| 安全模式 `-x` | 曾成功进入桌面，基本 GOP 显示 | 只证明这一退路可用，不是正常加速验证 |

当前正常启动 IORegistry 的 `WhateverXeNoAccelGuardReady=Yes`，说明禁用加速的保护钩子已就绪。WATCHDOG 采样中主线程等待渲染工作、多个 QuartzCore/软件绘制线程持续消耗 CPU；尚不能把这一观察等同于唯一根因。

本机系统为 Tahoe 26.7.1 / 25G241，使用 WhateverXe 0.5.0、Graphics 0.2.0、Lilu 1.7.3、AMFIPass Mod 1.4.1。安装日志确认 pkg 安装成功，版本满足上游 Tahoe 26.7+ 的条件，且机主已经在隐私设置允许扩展。

## 已核对的源码与二进制边界

报错文字存在于 Graphics 包的自定义 `XeCompilerAdapter.bundle/Contents/MacOS/adapter.dylib`，不是 OpenCore 的 EFI 启动错误。适配器 SHA-256：

```text
5e5b788afa4d5b314f5425f3083aba801573a0a5b6c93a4938bdae61a839401e
```

本地反汇编显示，该错误出口可以由输入长度/封装检查、属性扫描、函数转换及部分分配失败等多个分支到达。尚未拿到触发错误的实际 shader 输入和拒绝分支，不能认定一定是长度上限、某种 AIR 版本或某条沙盒日志。

日志还出现过编译器读取适配器和 IGC 资源的 sandbox deny；WEX 源码存在先调用原检查、再在限定条件下放行的路径，所以 deny 文本本身不能证明最终访问失败。

审查版本：WEX `c6cd8ec5ec5bd64ad3c8a852a30d1f537d819fb1`，Graphics `e83018e76c0f39f0f870ff38dcc304fb357c3485`。截至本次检查，最新发布仍是 [WEX 0.5.0](https://github.com/b00t0x/WhateverXe/releases/tag/0.5.0) 与 [Graphics 0.2.0](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.2.0)。发布记录没有提供本机这一错误的已验证修复。

Graphics 仓库的 [SOURCES.md](https://github.com/b00t0x/WhateverXe-Graphics/blob/e83018e76c0f39f0f870ff38dcc304fb357c3485/docs/SOURCES.md) 说明它从最终签名载荷构建安装包，并不重现完整提取、修改和签名过程；已检查的公开树没有这份适配器对应的 C/C++ 实现。

## 建议的处理顺序

1. **保留本次可启动、触控板正常的基线。** 当前去掉 `-wex-noaccel` 会重新进入已知有问题的加速路径，不能将这个操作叫作修复。
2. **先降低桌面效果作为临时对照。** 在系统设置的辅助功能中开启减少透明度、减少动态效果，使用静态壁纸；测试较低的实际输出分辨率。注意“看起来像”的 HiDPI 缩放可能采用更高的内部渲染分辨率，不能只看字号变大。该实验只能判断负载影响，不保证消除 WATCHDOG，也不恢复 Metal。[Apple 的显示和动态效果说明](https://www.apple.com/accessibility/features/)
3. **修复重点是捕获适配器输入。** 已准备 [原 adapter 的 LLDB 捕获与独立重放工具](../experiments/xe-compiler/README.md)，先在 macOS 验证附加权限并取得实际失败 shader；随后修复已定位的转换分支。若保护进程不可附加，仍需可调试环境或签名诊断版。当前没有真实输入，不把日志收集当作完成。没有代用户向上游发消息。
4. **需要更快取得可用系统时，做独立 OS 对照。** 上游也列出 Sequoia 15.8.x 为支持范围，可在独立测试目标验证；本机尚未证明它能稳定加速。不要覆盖当前系统，也不要改动受保护的原 APFS 数据分区。成功或失败都应保存版本、同一操作的结果和日志，才能区分 Tahoe 专有路径与更普遍的故障。[上游兼容表](https://github.com/b00t0x/WhateverXe/blob/0.5.0/README.md#compatibility)

另一项目的公开 compiler-adapter.cpp 已审查至 main `453a7b5`，相关编译器文件相对原 `b3f6b09` 未变化。入口布局相近，但它调用旧 plugin 的 WithOptions 和 Tahoe LLVM；当前 WEX 直接调用 AIR 后端，不能单文件替换。完整 [兼容性审查、源码哈希及验证状态](../experiments/xe-compiler/AUDIT.md) 已放在独立实验目录；尚未移植或部署替代驱动。

## 不应据此推导的修复

- DVMT 实际为 64MiB，尚未设为 96MiB。若 BIOS 提供选项，可以做 96MiB 对照；没有证据证明它能处理 bitcode 转换错误，也不能通过一个 plist 数值增加物理预分配。
- 切换 OpenCore RELEASE 已完成，不能继续把 WindowServer 故障归因于 OpenCore DEBUG 文件日志。
- pkg 安装成功与已允许扩展都有记录，重复安装或重复点击允许并不能解释已抓到的特定编译错误。
- 没有证据支持继续放宽 SIP/AMFI，或照抄其他设备 ID 的补丁；这些操作会增加变量。

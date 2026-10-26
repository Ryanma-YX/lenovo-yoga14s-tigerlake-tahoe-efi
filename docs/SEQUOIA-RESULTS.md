# Sequoia 15.8.1：启动、3D 与 App Store 视频冻结

2026-10-26，机主完成 Sequoia 15.8.1 / 24H32 安装和 Graphics 0.2.0 安装，从外接 SSD 自带的 OpenCore 启动。日志确认 Iris Xe 9A49、Metal 2、2880×1800 / 90Hz；机主确认可使用 3D。后续观察到 App Store 首页自动播放视频时冻结，隔离视频 VA 插件后能打开。

这是当前已验证的规避状态，不是全功能日用稳定结论。此前 Tahoe 的编译适配器错误保留为历史问题，不能套用为本次 Sequoia 的直接原因。

## 选择配置

仓库 `EFI/OC/config.plist` 及 `config-basic-display.plist` 保留原 Tahoe 归档。新的 Sequoia 配置位于：

| 配置 | 用途 |
|---|---|
| `profiles/config-sequoia-noaccel.plist` | 安装、初次进入桌面或无加速诊断；保留 `-wex-noaccel`。 |
| `profiles/config-sequoia-accelerated.plist` | 已安装匹配 Graphics 包后的 3D 配置；本机需同时隔离 VA 插件来规避 App Store 冻结。 |

两份 Sequoia 配置仅在 `-wex-noaccel` 上不同，身份字段均已脱敏。它们包含 Darwin 24 专用 AirportItlwm 条目，Tahoe 的同名 bundle identifier 条目只适用于 Darwin 25+，不会同时加载。

生成带有自己原有身份的副本：

```powershell
python tools/personalize.py --from-config "X:\your-original-config.plist" --profile sequoia-noaccel
```

需要加速时可在干净的输出目录使用 `--profile sequoia-accelerated`。工具仍拒绝覆盖已有 `build/EFI`。不要直接把空身份模板覆盖到现有机器 EFI，也不要重新生成已经登录使用的机器身份。

Sequoia 配置采用 `ProvideCurrentCpuInfo=true`、`SetupVirtualMap=false`，机主确认恢复这两项后仍能启动。保持 `AppleXcpmExtraMsrs=true` 和无 MAT 组合。该结果只证明这一组合可启动，不证明其他开关都无必要。

## 冻结证据

脱敏汇总来自本机采集的独立 GPU 重置、WindowServer 报告和统一日志；不提交原始日志。

- 21:09 的三份 GPU Reset 报告关联 `VTDecoderXPCServ`（报告中截断的视频解码服务名）。
- 21:29 的一份 GPU Reset 报告关联 App Store。
- 另有四份较早的 GPU Reset 关联图标服务。
- 四份 WindowServer 报告为 WATCHDOG code 1，包含画面未就绪、GPU Busy 或最长约 80 秒无法 checkin；堆栈进入 IOAcceleratorFamily2。
- 机主对照：关闭 3D 可打开 App Store；保留 3D、隔离 VA 插件后同样可打开。

这些证据支持视频加速路径触发 GPU 挂起并拖住桌面。未定位 H.264/HEVC、视频转色、画面拷贝或具体驱动指令。部分 ring dump 自报数据可能不可靠，不能据此单独认定某个物理引擎损坏。

## 规避与恢复

使用 [视频工具说明](../tools/graphics/README.md) 的 `disable`，校验后把完整 VA 插件移出加载目录。它影响硬件解码和编码，保留 Metal 插件及 3D EFI；执行后重启。`restore` 可还原完整原插件。仅在本机 Sequoia 15.8.x、五个文件匹配时执行。

安装/恢复环境仍可使用无加速配置。实机 EFI、小备份、磁盘身份、实际 SMBIOS、账户和原始报告均保留在本地。

## Apple Account 与采集边界

账户验证码后的失败没有足够日志定位。一批 Unknown error 124 / NSCocoaErrorDomain 4099 与会话退出及 `Domain is tearing down` 同时出现，不能当作 Apple 服务器拒绝账户。另有账户查询、配置 bag 与请求超时，不足以定位到机器身份或网络中的某一项。

第一版统一日志只保留最后 10,000 行，实际覆盖约 21:59–22:16，较早冻结依赖独立报告追溯。新版采集器保留选定时间段全部相关行，并加入视频服务和网络接口。账户后续应在 VA 已隔离的可用状态采集，不重新启用会挂起的路径。

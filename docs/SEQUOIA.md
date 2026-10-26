# Sequoia 原生 Recovery 安装

当前路线为 **SanDisk OpenCore → Apple Sequoia 原生 Recovery → Wi-Fi 联网安装**。现场操作见 [START-HERE.md](../START-HERE.md)，可用手机查看，不需要磁盘 GUID 或终端安装命令。

此前的 Sonoma Recovery + 本地完整包展开路线已停用。旧 Tahoe 系统已经由机主擦除，安装时直接选择原约 239GB 区域中的空系统卷，不再要求擦除。原约 273GB 数据分区和内部 Windows 盘继续保留。

## 恢复镜像

- Apple Recovery 产品：`093-10615`。
- 从镜像内 `SystemVersion.plist` 确认：Sequoia **15.6.1 / 24G90**。
- 镜像大小：888,615,275 字节。
- SHA-256：`c9fff24b410ae134c6be17ebd4194e0ad3d73bb839a65f8d94c93a20fe97cd1e`。
- OpenCore 原始 `macrecovery.py` 验证 Apple RSA chunklist 和全部 85 个分块。
- 查询使用最高支持 Sequoia 的 iMacPro board ID；下载查询不会修改本机 EFI 中的 SMBIOS。
- 恢复环境版本与联网实际安装版本可能不同，以安装界面和安装后的 `sw_vers` 为准。

`tools/sequoia/download_native_recovery.py` 从 Apple HTTPS 元数据服务获得恢复镜像地址和访问令牌，使用 API 返回的 Apple CDN 地址下载，再进行 Apple RSA 与全部分块校验。令牌、私有磁盘计划、恢复镜像和完整安装包均不加入 Git。

## EFI 与图形

沿用已准备的 OpenCore 1.0.8、触控板修复、真实 SMBIOS 和 Sequoia AirportItlwm 条目；USB 保留 `-wex-noaccel`。本次只替换恢复镜像和说明，不改动 SSK 的分区或 EFI。

AirportItlwm Sequoia 的实际 Recovery 联网能力仍需实机确认。Graphics 0.2.0 的 Sequoia 支持条件为 15.8.x；系统安装后先核对版本，必要时更新到支持版本，再安装图形包并验证 Metal。旧的 `Finish-Sequoia-USB.command` 固定要求 15.8.1 / 24H32，不能对未知安装版本直接执行。

## 历史工具

`Recovery-Install.command`、`USB-Install.command`、`Start-USB.command`、`Prepare-USB.command` 和缩容安装工具保留为历史源码，不用于当前联网安装。部署到 U 盘的旧离线入口已停用，避免误运行。

Windows 中的镜像签名、分块校验、U 盘文件读回与 EFI 静态检查，不代表原生 Recovery 联网、系统安装或 Metal 已验证。

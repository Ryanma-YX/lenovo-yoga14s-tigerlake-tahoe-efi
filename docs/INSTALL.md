# 安装与个性化

## 本仓库与实机原版的差别

为避免在 Git 历史中留下机器身份，`EFI/OC/config.plist` 和基础显示配置的以下内容已经清除：

- `PlatformInfo/Generic`：MLB、SystemSerialNumber、SystemUUID、ROM。
- NVRAM 中的蓝牙控制器缓存与标记。

其余引导设置、ACPI 与驱动二进制保留。需要自己的身份时，可以从已有本机配置生成副本：

```powershell
python tools/personalize.py --from-config "X:\path\to\your-original-config.plist"
```

输出为 `build/EFI`，该目录已在 `.gitignore` 中排除。不要把自己的身份配置或生成目录提交到仓库。也可用 OCAT / ProperTree 在本地副本中填入自己生成的、对应 `MacBookPro16,2` 的身份，再用匹配版本的 ocvalidate 检查。

这里没有自动查询 Apple 序列号服务，也没有自动生成或发布新的机器身份。

## 制作恢复启动盘

- 准备 GPT / FAT32 的 UEFI 启动介质。
- 使用 OpenCore 的 macrecovery 下载并验证配套 DMG / chunklist。
- 将生成的 `EFI` 放在启动分区根目录；将镜像与 chunklist 放入 `com.apple.recovery.boot`。
- 从 UEFI 启动菜单选择该介质，再选择 OpenCore 中的 `(dmg)` 入口。

不要把 `usr/standalone/OS.dmg.root_hash` 与 U 盘旁边的 `BaseSystem.chunklist` 当作同一种文件，不要通过重命名或创建空文件去伪造校验资料。

## 安装目标与数据保留

这次测试另外准备了外置 SSD 的独立新分区，原有 APFS 数据容器保留。新目标在 Windows 中暂标为 exFAT `TAHOESETUP`，进入安装环境后只将这个新目标抹掉为 APFS `Tahoe`，然后选它安装。

如果要保留磁盘上已有的 APFS 分区，不能照抄“抹掉整块物理磁盘”的步骤。也不要把 Windows 的磁盘编号当成 macOS 的 disk 编号；按设备、容量和卷标确认。

本仓库没有附带磁盘分区、删除卷或整盘抹除脚本。GPT 备份、APFS 抽样、磁盘序列号与私有分区操作记录保留在本地工作区，没有上传。

## 安装重启

保持启动 U 盘与目标 SSD 连接。每次通过同一个 OpenCore 引导；第一阶段重启后，选择 SSD 上新增的 `macOS Installer`，安装结束后选择系统卷。不要每次都重新选在线恢复镜像。

当前验证止于“进入安装界面”。完整安装和将 EFI 迁移到外置 SSD 的独立启动验证仍待完成。

## 使用基础显示配置

需要关闭 WhateverXe 排查时，可在本地副本中将 `profiles/config-basic-display.plist` 替换为 `EFI/OC/config.plist`，然后填入自己的身份。该配置只增加 `-wexoff`；恢复主配置时移除此参数即可。它没有单独的成功实机结论。

## 图形包

恢复环境中的画面不是 Metal 加速验证。按照归档时的上游要求，先安装/更新到符合 WhateverXe Graphics 要求的 macOS 构建，再在 macOS 内安装匹配的 Graphics pkg。不要在 Tahoe 26.6.2 中绕过 Graphics 0.2.0 的版本检查。

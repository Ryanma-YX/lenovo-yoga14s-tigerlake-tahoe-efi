# 重启后从这里看安装步骤

不需要记 GUID 或固定的 disk 编号。手机可以直接打开本页；U 盘的 SEQ-DATA 数据分区根目录也有同一份 START-HERE.txt。

当前已制作的 U 盘仍是 **Sonoma Recovery 宿主 + 本地 Sequoia 15.8.1 安装包**。讨论过的 Sequoia 原生 Recovery 在线方案尚未制作。以下步骤对应当前 U 盘，独立 Recovery 启动和安装过程仍待实机验证。

## 1. 从 U 盘启动

保持 SanDisk U 盘和 SSK SSD 都插着。固件启动菜单选择 SanDisk 的 UEFI/OpenCore，再选外部的 macOS Base System（dmg）。

Recovery 显示 Sonoma 是工具宿主的版本。**不要点“重新安装 macOS Sonoma”。**

## 2. 查看说明和安装目标

打开顶部菜单“实用工具 → 终端”。随时可以用下面一行查看 U 盘上的说明：

```bash
cat /Volumes/SEQ-DATA/START-HERE.txt
```

显示唯一允许替换的系统容器：

```bash
bash /Volumes/SEQ-DATA/INSTALL.command
```

脚本从 U 盘保存的计划自动读取 GUID，核对设备和分区后显示：

- `Replacement container`：允许替换旧 Tahoe 的容器。
- `PROTECTED data partition`：必须保留的数据分区。

磁盘编号每次可能变化，以当次输出为准，不凭记忆选择。

若提示找不到 SEQ-DATA，先打开磁盘工具，选中 SanDisk 下名为 SEQ-DATA 的 exFAT 卷并点击“挂载”，再回来执行。不需要输入 GUID。

## 3. 清空旧系统并启动 Sequoia 安装器

先确认数据卷已经挂载且完整包可读：

```bash
ls -lh /Volumes/SEQ-DATA/InstallAssistant.pkg
```

如果数据卷挂载失败、找不到安装包，或目标映射出现 STOP，先停止，不要抹旧系统。未挂载卷显示的 `Volume Total Space: 0` 不能当成分区实际大小；容量检查已改为读取分区表中的大小。GitHub 更新不会自动更新已制作的 U 盘脚本。

打开磁盘工具，选择“显示所有设备”。仅在脚本标出的替换容器内，选中旧 Tahoe 系统卷，使用“抹掉卷宗组”，命名 **Sequoia**、格式 **APFS**。

保留约 273GB 数据分区和内部 Windows 盘。不要抹整个 SSK、整个 APFS 容器或 SanDisk U 盘。

回到终端：

```bash
bash /Volumes/SEQ-DATA/INSTALL.command install
```

脚本再次核对磁盘身份，检查本地完整包和 Apple 原生签名，展开匹配的 Sequoia 安装 app，再打开安装窗口。只选择刚才新建的 Sequoia 卷。出错则停止并保留终端输出。

完整系统包已在本地，但 Apple 安装器仍可能要求联网验证；Recovery 中 AX201 网络尚未实测。

## 4. 安装重启及启用显卡

安装重启时继续从 SanDisk OpenCore 启动，先选目标 SSD 上的 macOS Installer，最终进入 Sequoia。两只外接设备保持连接。

进入 Sequoia 桌面后，在终端执行：

```bash
bash /Volumes/SEQ-DATA/INSTALL.command finish
```

后处理会校验实际系统和目标 SSD，安装本地 Graphics 包，并更新 SSK 的 Sequoia Wi-Fi/加速配置。若提示，先批准系统扩展，再重启从 SSK OpenCore 测试加速。

SanDisk OpenCore 保留无加速恢复入口。系统安装成功、Metal 实际运算和桌面稳定性需要分别验证。

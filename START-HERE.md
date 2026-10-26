# Sequoia 原生 Recovery 联网安装

当前使用 Apple 原生 **Sequoia Recovery 15.6.1 / 24G90**，联网下载并安装系统。实际可安装版本以 Apple 安装界面为准。

不需要运行 INSTALL.command，不需要挂载 SEQ-DATA，不需要输入磁盘 GUID。原 Tahoe 系统已经擦除，直接使用已准备的空系统卷，不再擦盘。

1. 保持 SanDisk U 盘和 SSK SSD 插着。固件启动菜单选择 **SanDisk UEFI / OpenCore**，再选 U 盘上的 **macOS Base System（dmg）**。
2. 进入恢复界面后，从右上角 Wi-Fi 菜单连接网络。选择 **重新安装 macOS Sequoia**。若仍显示“重新安装 Sonoma”，说明启动了旧恢复镜像，先不要安装。
3. 安装目标选择 **SSK 原约 239GB 区域中已经擦除的空系统卷**。如果卷名是 Sequoia，就选择 Sequoia。保留另一个约 273GB 数据区和内部 Windows 盘，不要再次抹整个磁盘或 APFS 容器。
4. 等待 Apple 联网下载并安装。安装期间两只外接设备保持连接。
5. 自动重启时继续从 **SanDisk OpenCore** 启动，先选目标 SSD 的 **macOS Installer**，最终进入 **Sequoia**。

安装期间保留无加速配置。系统安装完成后，再核对系统版本、安装匹配的 Graphics 包并验证显卡。现有 Graphics 0.2.0 的 Sequoia 要求为 15.8.x；如果装出的版本较旧，先更新系统，不直接运行旧的版本固定后处理脚本。

恢复镜像的 Apple RSA 签名与全部 85 个分块已校验；Wi-Fi 在该原生 Recovery 中的可用性、实际安装结果和显卡加速仍需实机确认。若 Wi-Fi 不可用，记录恢复界面情况，不要运行此前的离线安装脚本。

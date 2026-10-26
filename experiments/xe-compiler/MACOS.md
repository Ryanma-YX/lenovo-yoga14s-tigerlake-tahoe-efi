# 下一次切回 macOS：一次取证流程

目的：拿到真实失败请求的 bitcode、request、Create 硬件参数和拒绝跳转。单纯生成系统日志不能完成此目标。以下 macOS 步骤尚未在本机执行；权限拒绝和编译失败都必须保留实际结果。

## 1. 在当前可启动基线准备

保留 `-wex-noaccel` 及触控板配置。把此目录的文本源码复制到 macOS 的用户目录，例如 `$HOME/xe-compiler`。不要把整个参考项目 EFI 或 Apple 载荷覆盖到系统。

需要 Xcode Command Line Tools 的 clang、LLDB、SDK；Python 3 用于校验和重放。先执行：

```bash
cd "$HOME/xe-compiler"
bash preflight-macos.sh "$HOME/xe-private-preflight-20261026"
bash build-macos.sh
python3 -m unittest discover -s tests -v
```

preflight 只创建新的私有输出目录，读取版本、符号、依赖和签名，使用 ditto 备份**完整 XeCompilerAdapter.bundle**（原适配器、后端、runtime、Info.plist、签名及扩展属性），不写驱动目录。查看 `signature-status.txt`，不要因脚本走到结尾便认定签名通过。离线重放优先使用系统原位置；副本可能受到路径或签名加载限制。

备份与捕获均保留本地。当前不部署任何新 bundle，所以不需要恢复系统文件；这份备份为后续经审核的部署提供原始文件。它不是整个 EFI/Metal/kext 栈的备份，未来若修改那些组件还必须分别备份。此流程没有任何磁盘分区或 EFI 写入命令。

可在此模式运行 `./build/metal-smoke`，预期可能是 `NO_METAL_DEVICE`。这只能作为基线记录。不要为了让 smoke 成功便直接修改当前唯一可启动配置。

## 2. 安排一次加速复现

原 bitcode 故障发生在加速路径。持续使用 `-wex-noaccel` 很可能没有相关请求可抓。

先准备已验证可启动的原 EFI 退路；若要试加速，用独立测试启动介质的本机私有 EFI 副本，只移除该副本的 `-wex-noaccel`。保留自己身份、所有触控板和引导设置。仓库脱敏 config 不能覆盖实机身份。不操作内部 Windows NVMe，不调整任何 APFS 分区，不使用固定磁盘编号。

黑屏时需要另一个终端入口：先在基线启用并验证系统自带 Remote Login，通过另一台设备连接；或者使用已经验证可用的文本控制台。不要等进不了登录桌面才准备连接。这个实验不自动修改远程登录或重启设置。

复现启动后，尽早在登录屏幕阶段附加编译服务。LLDB 会暂停进程，可能影响桌面；不要根据调试过程判断原始 WATCHDOG 是否修复。记录一次短复现，随后 detach。

## 3. LLDB 捕获（不会替换 dylib）

先确认当前服务 PID，多个同名服务时按实际进程选择：

```bash
pgrep -lf MTLCompilerService
sudo xcrun lldb
```

LLDB 中，下列绝对路径替换成自己的用户名路径。若服务已经存在：

```text
process attach --pid 实际PID
command script import /Users/自己的用户名/xe-compiler/lldb_capture.py
xe-arm /Users/自己的用户名/xe-private-capture-20261026
continue
```

捕获目录必须是新的绝对路径。脚本仅给 `adapter.dylib` 建立入口断点；加载后检查文件 SHA-256 与运行映像 UUID，随后设置内部位置。`breakpoint list` 可确认是否仍 pending。没有命中不等于请求已经抓到。

如需在新服务启动时尽早捕获 Create，可在 LLDB 中先建 service target、导入和 arm，再等待：

```text
target create --arch x86_64 /System/Library/Frameworks/Metal.framework/Versions/A/XPCServices/MTLCompilerService.xpc/Contents/MacOS/MTLCompilerService
command script import /Users/自己的用户名/xe-compiler/lldb_capture.py
xe-arm /Users/自己的用户名/xe-private-capture-fresh-20261026
process attach --name MTLCompilerService --waitfor
continue
```

等待只针对下一次启动；不会自动杀掉已有服务。XPC 实际启动时机、多个实例与附加权限均可能影响结果。若已错过 Create，request 捕获仍可用于分支/封装分析，但不会产生可靠的硬件重放参数。

从另一个终端运行 `./build/metal-smoke` 或执行已知触发桌面错误的操作。smoke 是小 compute workload，不声称能重现 `Pl64rXb_TdfgXhf_Isrc`。若原来失败的请求来自其他服务 PID，需要对该实例重新捕获。

在 LLDB 按 Ctrl-C 后结束本次实验：

```text
xe-disarm
process detach
quit
```

这会移除本工具断点并恢复进程运行。不要使用 `process kill`。回调报 `xe capture stopped` 时，进程停住，尽快执行相同 detach 步骤。达到 64 个请求也会停止；重新开 LLDB 和新目录才开始另一轮。

若附加提示 operation not permitted、task port 拒绝或调试器不可用，保存那条错误并结束此分支。当前没有证据支持继续放宽 SIP/AMFI，也没有通过 ad-hoc 重签服务的步骤。此时仍没有真实 shader 样本，下一步需可调试环境或维护者提供签名诊断版；已有日志不能代替样本。

## 4. 校验与独立重放

每个 `request-xxxx` 目录预期包含：

| 文件 | 为什么需要 |
| --- | --- |
| `capture.json` | 参数长度、哈希、返回值、错误文本、实际采用的拒绝分支、扫描/转换返回状态 |
| `bitcode.bin` | 原始 serialized bitcode 输入，修复及回归的关键样本 |
| `request.bin` | 与 shader 对应的实际 0xD8 字节请求 |
| `hw.bin` | 与同一个 compiler 关联的 Create 原始 0x80 字节；可能缺失 |

`result: null` 表示未观察到正常返回；不能算成功。`errors` 非空、文件缺失或哈希不符也不能当成完整样本。`rejections` 提供分支信息，`error_text` 对照 layout 错误。如果只抓到成功的 smoke 请求，仍未拿到桌面失败 shader。

```bash
python3 capture_format.py "$HOME/xe-private-capture-20261026/request-0001"
python3 run_replay.py "$HOME/xe-private-capture-20261026/request-0001"
```

校验器在 Windows/WSL 也可运行；它只判断完整性和外层封装。`passed-envelope-only` 不是 LLVM parser 或转换成功。

重放器要求 x86_64 macOS、同哈希 adapter、完整 hardware 和 0xD8/flags=0 请求。运行独立子进程，默认 30 秒超时；真实后端崩溃由操作系统处理，不用 siglongjmp 恢复。未经分析的 request 可能含私有布局/地址，独立重放仍可能失败；失败本身需要与 LLDB 分支对照。独立程序的加载成功不证明 sandbox 内的 MTLCompilerService 能加载，也不证明同一 shader 编译结果完全一致。

若能重放 layout 错误，可进一步给 runner 附加同一套 LLDB 命令，在固定输入上追踪 `_xe_scan_attrs` / `_xe_sonoma_functions` 的更深子分支，然后才设计最小转换修改。runner 返回 0 也只证明这次编译调用返回成功，不证明 GPU 正确执行。

## 5. 验收与带回资料

将真实结果分别记录为：macOS 构建、独立程序签名、LLDB 可附加、原 adapter 重放、服务加载、Metal 读回、原 CoreAnimation 故障和登录稳定性。不要跨层合并成一个“通过”。

这次最需要带回本地工作区的是完整失败 `request-xxxx`、preflight 的版本/导出/依赖/签名文本、LLDB 的权限或脚本错误、smoke 的退出码与输出。完整 bundle 备份留在 macOS 本地即可。不要上传原始 `.ips/.spin`、SMBIOS、ROM、蓝牙缓存、凭证、Apple bundle 或未经审查的 shader。所有捕获均默认私有；没有自动上传步骤。

完成后从保留的基线 EFI 启动，继续使用 `-wex-noaccel`。若没有修改任何驱动，只需退出调试器与测试程序；不执行重新安装、重签或系统快照回滚。

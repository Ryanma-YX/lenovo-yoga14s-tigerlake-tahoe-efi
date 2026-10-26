# Xe 编译器诊断实验

状态：2026-10-26，**仅完成 Windows 静态审查与 WSL CPU mock 验证**。未构建、签名、安装替代 adapter；未取得本机失败 shader；macOS 的 LLDB 回调、原 adapter 重放及 Metal 测试均待实测。

实验位于独立分支 `experiment/xe-compiler-capture-20261026`。EFI、触控板、启动参数和签名驱动均不变。兼容性证据见 [AUDIT.md](AUDIT.md)，切回 macOS 操作见 [MACOS.md](MACOS.md)。

## 最小路线

先用 LLDB 调试原始签名 adapter，从实际请求读取 request/bitcode/hardware 参数，并在已核对的拒绝跳转位置记录 CPU flags。文件由调试器写入私有目录，避免为导出数据而修改编译服务的沙盒或安装新的 dylib。

这不是“已经取得样本”：只有生成完整 `bitcode.bin`、`request.bin` 和有效 `capture.json` 才是请求捕获；必须再关联非零返回值、错误文本、拒绝分支，才能称为失败输入。`hw.bin` 缺失时可以离线检查封装，但重放工具拒绝猜测硬件结构。

不直接移植外部 CPP 的原因是后端契约不同：WEX 的 `libigc-tgl.dylib` 没有该 CPP 调用的旧 plugin 入口，完整移植还需要旧 Apple plugin、LLVM bridge、资源、签名及沙盒适配。尚无证据证明这些改动能处理本机失败输入。

## 文件与验证

| 文件 | 用途 |
| --- | --- |
| `lldb_capture.py` | 精确入口、七个输出槽、14 个拒绝跳转、线程与返回栈关联 |
| `capture_format.py` | 长度、SHA-256、BOM、固定文件名校验；仅检查 LLVM 外层封装 |
| `replay.cpp` / `run_replay.py` | 原 adapter 的独立子进程重放；超时结束；不拦截崩溃继续运行 |
| `metal-smoke.m` | 实机编译一个 compute shader、提交及读回 4 个整数 |
| `preflight-macos.sh` | 读取版本、导出、依赖与签名状态；备份完整 compiler bundle |
| `build-macos.sh` | 构建两个独立用户态程序；只签它们，不签 Apple 后端 |
| `audit_binary.py` | 原 Mach-O 的哈希、依赖和编译器符号清单 |
| `audit_reference.py` | 固定上游版本、源码哈希、最新提交差异 |
| `audit_offsets.py` | 可选 Capstone 校对断点指令；需本地原始 adapter |

本次通过：Python 4 项测试；原始二进制的 14 个跳转位置静态核对；g++ + ASan/UBSan mock 的 13 参数调用、失败返回和 borrowed error 处理；Bash 语法；原 EFI 的身份脱敏、文件哈希及两份 ocvalidate 检查。

```powershell
python -m unittest discover -s experiments/xe-compiler/tests -v
python tools/validate_efi.py
```

WSL Ubuntu 中：

```bash
cd /mnt/d/LocalMCP-Test/lenovo-yoga14s-tigerlake-tahoe-efi/experiments/xe-compiler
python3 tests/run_cpu.py
bash -n build-macos.sh preflight-macos.sh
```

mock 只检查我们声明的调用和文件处理，不证明 Apple 私有 ABI 正确，更不等于 macOS 构建或 shader 编译成功。原 Mach-O 中存在签名命令也不等于签名验证通过；两个 profile 的 `signature_verified` 均为 false。

## 数据与来源

真实捕获放在仓库外的私有目录。`captures/`、`local/`、`build/` 和 `.bin/.bc/.dylib/.ips/.spin/.log` 被忽略；不要 `git add -f`。捕获内容可能有进程地址、shader 中的应用数据及路径，不能自动认定已经脱敏。备份中包含 Apple 文件，不上传。

此目录的诊断代码独立实现，没有复制外部 adapter/bridge 源码。上游仓库根许可证为 **Thou Shalt Not Profit License 1.0**；其源码“可查看”不表示 BSD。相关许可原文、版本与来源见 [AUDIT.md](AUDIT.md)。

不存在驱动部署命令。回退本实验是 `xe-disarm`、`process detach`；退出独立程序即可。未来任何替代 bundle 的部署，需要先解决签名身份、确切路径与回退引导，另行审核。

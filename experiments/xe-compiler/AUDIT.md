# compiler-adapter.cpp 与 WEX 的兼容性审查

## 判断

**可以把外部源码作为完整替代编译链的研究起点；现有证据不支持把它编译后直接覆盖 WEX adapter。** 当前应先捕获原 adapter 的失败请求，再决定修补转换器还是移植完整 plugin/LLVM 链。没有把独立转换器或替代 adapter 标为已完成。

2026-10-26 检查到外部 main 为 `453a7b5222d1e3f7f26c948feeaedc8f71d058b3`，父提交就是原审查的 `b3f6b09af1a60093c0d953211469d0ef1fbd1847`。新增提交改 OLED AUX 亮度；adapter、bridge、构建脚本、旧 plugin patch、METAL 文档及 LICENSE 均字节不变。可复现记录：[reference-profile.json](reference-profile.json)。[最新提交](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/453a7b5222d1e3f7f26c948feeaedc8f71d058b3)

## ABI：入口相近，后端完全不同

本次重新读取原始 Mach-O 并对照反汇编。WEX adapter SHA-256 为 `5e5b788afa4d5b314f5425f3083aba801573a0a5b6c93a4938bdae61a839401e`；UUID 为 `6FC99E91-0EFE-326E-B284-1FDE610D1697`。

| x86_64 SysV 位置（函数刚进入时） | 静态观察及含义 |
| --- | --- |
| RDI | WEX 自己的 compiler/context 指针 |
| RSI | request 指针 |
| RDX | request 字节长度；在 `0x13e2` 与 `0xD8` 比较 |
| ECX | flags；在 `0x13ec` 要求为 0 |
| R8 / R9 | serialized bitcode 指针 / 字节长度；保存于 `0x12d4..0x12d8` |
| entry RSP+8、+16、+24、+32、+40、+48、+56 | 7 个指向输出槽的指针，prologue 后分别位于 RBP+0x10..0x40；入口全部清零 |
| 第 7 个输出槽 | 错误字符串指针；`0x168b` 写入共用错误文本 |

所以 0xD8 是 request 的大小，不是参数数量、调用帧大小或 bitcode 固定长度。7 个输出槽都要提供；独立 runner 为每个分配 `uintptr_t`，不会凭名字构造不明 C++ 对象。第 1/2 个槽按回复指针/长度使用，但其余槽的完整语义仍未确认。返回值在本路径由 EAX 给出 0/1；完整跨版本私有 ABI 尚未实机验证。

外部 [compiler-adapter.cpp](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/453a7b5222d1e3f7f26c948feeaedc8f71d058b3/macos/src/compiler-adapter.cpp) 声明的 serialized 入口也是 13 参数。它将 bitcode 解析为 Tahoe LLVM Module，把新入口的第 7 个参数移至旧入口 R9，后续堆栈参数前移，再额外传 null。因此入口寄存器布局有相符证据；**这不证明旧 plugin 对象能替代 WEX context。**

| 项目 | WEX 当前二进制 | 外部 adapter/脚本 |
| --- | --- | --- |
| 对外生命周期 | Create、BuildSerialized、ReleaseReply、Delete 四个导出 | 自定义 Create/Build；通过 re-export old plugin 提供其他入口 |
| Create 对象 | 分配 0x160 字节自己的状态，检查 hw 首字段 0x21 | 调用旧 plugin Create，再安装自制 ICB helper |
| 后端 | dlsym `CreateShaderCompilerAIR`、`CompileCSAIRFn`、VS/PS 及删除函数 | 直接调用 `MTLCompilerBuildRequestWithOptions` |
| LLVM | adapter 本身只链接 libSystem，内置 bitstream 转换 | 链接 Tahoe 32023，并为旧 plugin 提供 3902 bridge |
| 资源 | 同目录 `libigc-tgl.dylib`、`runtime.igc64.bc`，校验后端完整哈希和 runtime | xe.bundle 下的多个 dylib、split runtime 及 Resources |

本地 Tahoe 后端哈希为 `a27eaea380aee524a1972927cb44774da1affe0cea93e94c307927f38d41aaf4`。其编译器符号清单有 AIR API，没有外部 CPP 所需的 MTLCompiler WithOptions/Create plugin API。因此不能通过改一个 dlopen 路径接到当前后端。导出清单与依赖见 [adapter-profile.json](adapter-profile.json)、[backend-profile.json](backend-profile.json)；这是静态符号表检查，没有声称运行过 macOS 的 dlsym。

WEX Create 从硬件参数读取到 +0x78 的 8 字节，诊断器保存原始 0x80 字节。ReleaseReply 接收 compiler，释放其 +0x10 保存的 reply；错误文本在此失败分支是借用的静态字符串。runner 不 delete/free 错误文本，也不会传 reply 指针给 ReleaseReply。外部源代码在其异常路径使用 new[] 分配字符串，不能据此套用 WEX 的所有权契约。

## LLVM bridge 的移植工作量

已完整读取 [llvm-bridge.cpp](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/453a7b5222d1e3f7f26c948feeaedc8f71d058b3/macos/src/llvm-bridge.cpp)。它不只是重新导出三个符号：还实现 Twine 布局转换、parseIRFile 回调桥接、旧 raw_string_ostream 布局处理，并扫描 MTLCompiler 的私有 `getSerializedModule`。文件顶部“三个符号”的注释不足以代表当前实现。

具体约束包括旧 ostream 的 +0x28 `std::string*`、旧 Twine kind 位 +0x10/+0x11、新 Twine kind 位 +0x20/+0x21、手工 Optional/function_ref 布局。私有函数通过 prologue 与 3901/3902 比较常量定位，要求只有一个候选；找不到时回退 C API 序列化。该回退不证明能产生 IGC 3902 可读的 bitcode。

没有本机实际失败输入、运行系统 libLLVM 的完整导出/版本和旧 plugin 的对应二进制验证，无法保证跨 LLVM 的 C++ 类布局安全。独立实现必要转换也必须先有该失败样本，否则只能盲猜缺失的 AIR/bitstream 规则。

外部源码另有未原样采用的诊断行为：parse 失败返回 0；未见对应 LLVM context/module/buffer 清理；全局非原子计数；未知 request 长度时回退读取 0x400 字节；进程级信号处理器与 siglongjmp；dump 200000 字节上限；编译前 250ms 延时；noop ICB helper。它们都需要重新评估，不能当作稳定的 WEX 生产实现。

## 路径、签名和沙盒

外部 [build-shader-compiler.sh](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/453a7b5222d1e3f7f26c948feeaedc8f71d058b3/macos/build-shader-compiler.sh) 修改旧 plugin 的 load command 和 12 项字节 patch，重定向资源，重签所有复制出的 dylib。[METAL.md](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/453a7b5222d1e3f7f26c948feeaedc8f71d058b3/docs/METAL.md) 描述 xe.bundle 的路径注册/沙盒安排及 ad-hoc 使用条件；这些是该项目部署条件，没有在本机验证。

WEX 的 [kern_xe_data_policy.hpp](https://github.com/b00t0x/WhateverXe/blob/c6cd8ec5ec5bd64ad3c8a852a30d1f537d819fb1/WhateverXe/kern_xe_data_policy.hpp) 只为固定 MTLCompilerService 路径和特定文件提供例外：adapter、libigc-tgl、runtime、Info.plist 等。新增 bridge 或 old plugin 文件名不在该例外内。不能直接从这里断言它们最终必被拒绝，因为原 sandbox 也可能允许；必须通过实际加载结果验证，不能用 deny 日志单独判定。

Graphics [SOURCES.md](https://github.com/b00t0x/WhateverXe-Graphics/blob/e83018e76c0f39f0f870ff38dcc304fb357c3485/docs/SOURCES.md) 要求保留 Apple 后端字节不变、采用 Mod 签名。仅有 AMFIPass Mod 不能证明任意 ad-hoc 新 plugin 都能加载；本地没有已确认可用的 Mod 私钥。未来若做完整移植，必须先准备完整 bundle、明确依赖和签名身份，再分别验证 codesign、dyld、sandbox、真实 shader。当前实验没有放宽 SIP、AMFI 或内核路径例外。

## 为什么先用原 adapter 取证

哈希锁定后，LLDB 在实际函数入口读取六个寄存器和七个堆栈参数，绑定线程 ID 与返回时的栈位置，避免把另一调用的结果配错。捕获 Create 的原 hardware 参数，并按 compiler 对象关联；错过 Create 时显式标为缺失。

14 个条件跳转已经逐一与原始文件指令核对：[offset-audit.json](offset-audit.json)。在跳转执行前读取 RFLAGS，只有分支确实会被采用才记录拒绝原因，包括外层长度、wrapper、magic、分配、属性扫描/状态、函数转换和后端 parser。属性扫描与转换的返回 EAX 一并记录。可以区别共用文本下的不同分支，但尚未深入扫描器内部每一个子分支。

调试器拥有读取权限、进程可附加及断点行为都必须在 macOS 验证。软件断点会临时改指令字节并暂停线程，可能改变时序、引发 WATCHDOG；不把调试下的桌面稳定性作为结论。捕获错误会停在调试器，需主动 detach；不会自动跳过原错误或篡改返回值。

## 现有诊断复核与验收状态

重新按多 JSON 对象格式解析指定 crashes 目录，忽略 AppleDouble：13 个唯一 WindowServer COREANIMATION code 4 报告包含 layout 错误；2 个 WATCHDOG code 1 报告不包含该文本。先前“11 份”是更早审查数量。没有从这些报告提取到可重放 shader。

| 层级 | 本次结果 |
| --- | --- |
| 源码／静态 Mach-O 与 14 个分支位置核对 | 通过，已保存可复查摘要 |
| Windows Python 格式／模拟回调测试 | 4 项通过 |
| WSL g++ + ASan/UBSan CPU mock | 通过，仅验证自写 runner 与 mock 契约 |
| macOS clang/SDK 编译 | 未执行 |
| macOS codesign 验证 | 未执行；签名命令存在不算通过 |
| 原 adapter 的 LLDB 捕获、真实输入重放 | 未执行 |
| 新 adapter 签名、加载 | 无替代产物，未执行 |
| Metal compute 读回／CoreAnimation／登录稳定性 | 未执行 |

原始 Apple 文件、崩溃报告、进程数据、身份配置均未加入此实验；摘要只保留公开组件版本、符号与哈希。

外部根 [LICENSE](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/453a7b5222d1e3f7f26c948feeaedc8f71d058b3/LICENSE) 写明 TSNPL 1.0；不是 WEX 的 BSD 3-Clause。本次没有复制或重新许可其实现。后续若形成移植分发件，应按该原文核对来源、署名和分发要求。

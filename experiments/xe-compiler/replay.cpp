// Independent diagnostic runner for the audited WEX ABI, not a replacement plugin.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

static std::vector<unsigned char> read(const std::string& path, size_t max) {
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f) throw std::runtime_error("Cannot open capture blob");
    auto n = f.tellg();
    if (n < 0 || static_cast<uint64_t>(n) > max) throw std::runtime_error("Blob too large");
    std::vector<unsigned char> data(static_cast<size_t>(n));
    f.seekg(0);
    if (n && !f.read(reinterpret_cast<char*>(data.data()), n)) throw std::runtime_error("Short blob");
    return data;
}

template<class F> static F symbol(void* lib, const char* name) {
    auto p = dlsym(lib, name);
    if (!p) throw std::runtime_error(std::string("Missing symbol: ") + name);
    return reinterpret_cast<F>(p);
}

int main(int argc, char** argv) {
    if (argc != 4 || std::strcmp(argv[1], "--validated-capture")) {
        std::fprintf(stderr, "Use run_replay.py; raw interface: --validated-capture adapter directory\n");
        return 64;
    }
    try {
        const std::string dir = argv[3];
        auto hw = read(dir + "/hw.bin", 0x80);
        auto request = read(dir + "/request.bin", 0xd8);
        auto bc = read(dir + "/bitcode.bin", 16 * 1024 * 1024);
        uint32_t family = 0;
        if (hw.size() >= 4) std::memcpy(&family, hw.data(), 4);
        if (hw.size() != 0x80 || request.size() != 0xd8 || family != 0x21 || bc.empty())
            throw std::runtime_error("Unexpected capture sizes/target");
        void* lib = dlopen(argv[2], RTLD_NOW | RTLD_LOCAL);
        if (!lib) { std::fprintf(stderr, "dlopen failed: %s\n", dlerror()); return 70; }
        using Create = void* (*)(void*);
        using Cleanup = void (*)(void*);
        using Build = int (*)(void*, const void*, size_t, uint32_t, const void*, size_t,
                             uintptr_t*, uintptr_t*, uintptr_t*, uintptr_t*, uintptr_t*, uintptr_t*, uintptr_t*);
        auto create = symbol<Create>(lib, "MTLCompilerCreate");
        auto build = symbol<Build>(lib, "MTLCompilerBuildRequestWithSerializedBitcode");
        auto release = symbol<Cleanup>(lib, "MTLCompilerReleaseReply");
        auto destroy = symbol<Cleanup>(lib, "MTLCompilerDelete");
        void* compiler = create(hw.data());
        if (!compiler) throw std::runtime_error("Compiler allocation failed");
        uintptr_t out[7] = {};
        const int result = build(compiler, request.data(), request.size(), 0, bc.data(), bc.size(),
                                 &out[0], &out[1], &out[2], &out[3], &out[4], &out[5], &out[6]);
        // Do not free the error string. Original adapter returns borrowed/static text.
        // Avoid dereferencing opaque output pointers or publishing raw request contents.
        std::printf("adapter_result=%d reply_bytes=%llu error_present=%d\n", result,
                    static_cast<unsigned long long>(out[1]), out[6] != 0);
        release(compiler);
        destroy(compiler);
        dlclose(lib);
        return result == 0 ? 0 : 1;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "replay refused: %s\n", e.what());
        return 65;
    }
}

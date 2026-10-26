// CPU ABI test only. This library does not compile shaders.
#include <cstdint>
#include <cstdlib>
#include <cstring>
extern "C" void* MTLCompilerCreate(void* hw) {
    uint32_t family = 0; std::memcpy(&family, hw, 4);
    return family == 0x21 ? std::malloc(1) : nullptr;
}
extern "C" int MTLCompilerBuildRequestWithSerializedBitcode(
    void* comp, const void* req, size_t n, uint32_t flags, const void* bc, size_t len,
    uintptr_t* a, uintptr_t* b, uintptr_t* c, uintptr_t* d, uintptr_t* e, uintptr_t* f, uintptr_t* g) {
    if (!comp || !req || n != 216 || flags || len != 4 || std::memcmp(bc, "BC\xc0\xde", 4)) std::abort();
    if (a == b || b == c || c == d || d == e || e == f || f == g) std::abort();
    *a = 0; *b = 0; *c = 0; *d = 0; *e = 0; *f = 0;
    *g = reinterpret_cast<uintptr_t>("synthetic failure");
    return 1;
}
extern "C" void MTLCompilerReleaseReply(void*) {}
extern "C" void MTLCompilerDelete(void* p) { std::free(p); }

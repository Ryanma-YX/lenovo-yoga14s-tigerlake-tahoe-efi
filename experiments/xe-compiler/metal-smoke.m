// Small real Metal operation for the next macOS session; not the CA failing shader.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
int main(void) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) { fprintf(stderr, "NO_METAL_DEVICE\n"); return 2; }
        NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\nkernel void xe_test(device uint* out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = i * 7u + 3u; }";
        NSError *error = nil;
        id<MTLLibrary> lib = [device newLibraryWithSource:source options:nil error:&error];
        if (!lib) { fprintf(stderr, "LIBRARY_FAILED: %s\n", error.description.UTF8String); return 3; }
        id<MTLFunction> fn = [lib newFunctionWithName:@"xe_test"];
        id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:fn error:&error];
        if (!pipeline) { fprintf(stderr, "PIPELINE_FAILED: %s\n", error.description.UTF8String); return 4; }
        id<MTLBuffer> buffer = [device newBufferWithLength:16 options:MTLResourceStorageModeShared];
        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLCommandBuffer> command = [queue commandBuffer];
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        if (!buffer || !queue || !command || !encoder) { fprintf(stderr, "ALLOCATION_FAILED\n"); return 5; }
        [encoder setComputePipelineState:pipeline];
        [encoder setBuffer:buffer offset:0 atIndex:0];
        [encoder dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(4, 1, 1)];
        [encoder endEncoding];
        [command commit];
        [command waitUntilCompleted];
        if (command.status != MTLCommandBufferStatusCompleted) {
            fprintf(stderr, "GPU_FAILED: %s\n", command.error.description.UTF8String); return 6;
        }
        const uint32_t *values = buffer.contents;
        for (uint32_t i = 0; i < 4; ++i) {
            if (values[i] != i * 7 + 3) { fprintf(stderr, "READBACK_MISMATCH\n"); return 7; }
        }
        puts("METAL_COMPUTE_READBACK_PASSED (not CoreAnimation/login qualification)");
        return 0;
    }
}

"""LLDB commands: xe-arm PRIVATE_NEW_DIRECTORY; xe-disarm.

Reads the original process through the debugger, never writes target data or
changes a return value. Software breakpoints do temporarily patch instructions.
No DYLD injection, ad-hoc replacement, exception handler or sandbox alteration.
"""
import importlib.util
import json
from pathlib import Path
import shlex
import struct
import sys

import lldb

_spec = importlib.util.spec_from_file_location('xe_capture_format', Path(__file__).with_name('capture_format.py'))
fmt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fmt)
ROOT = None
BP = set()
RET = {}
ACTIVE = {}
HW = {}
MODULES = set()
COUNT = 0
LIMIT = 64
# File virtual addresses, not load addresses. Every site is an observed Jcc.
# Record a rejection only if its actual CPU flags make that branch taken.
SITES = {
    0x1426: ('jne', 'null-bitcode-or-length'),
    0x143a: ('jb', 'wrapper-short'),
    0x1445: ('jne', 'wrapper-version'),
    0x1461: ('jne', 'wrapper-offset'),
    0x147a: ('jne', 'wrapper-size'),
    0x1495: ('jb', 'raw-short'),
    0x14a4: ('jne', 'raw-magic'),
    0x14ba: ('je', 'input-allocation'),
    0x14e3: ('je', 'scan-allocation'),
    0x1552: ('je', 'attribute-scan'),
    0x1575: ('jne', 'attribute-state'),
    0x159a: ('je', 'function-conversion'),
    0x15c4: ('je', 'parser-allocation'),
    0x15fc: ('je', 'backend-parser'),
}


def taken(kind, flags):
    return {'je': bool(flags & 0x40), 'jne': not bool(flags & 0x40),
            'jb': bool(flags & 1)}[kind]


def reg(frame, name):
    value = frame.FindRegister(name)
    if not value.IsValid() or value.GetError().Fail():
        raise ValueError('Cannot read register ' + name)
    return value.GetValueAsUnsigned()


def memory(process, addr, size):
    if not addr or not 0 < size <= fmt.MAX_BLOB:
        raise ValueError('Null address or capture limit exceeded')
    err = lldb.SBError()
    data = process.ReadMemory(addr, size, err)
    if err.Fail() or len(data) != size:
        raise ValueError('Short/inaccessible process memory: ' + str(err))
    return data


def word(process, addr):
    return struct.unpack('<Q', memory(process, addr, 8))[0]


def save(folder, meta):
    temp = folder / 'capture.json.tmp'
    temp.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    temp.chmod(0o600)
    temp.replace(folder / 'capture.json')


def add_bp(target, address, callback, tid=None):
    b = target.BreakpointCreateByAddress(address)
    if not b.IsValid() or b.GetNumLocations() != 1:
        raise ValueError('Cannot place exact breakpoint')
    b.SetScriptCallbackFunction(__name__ + '.' + callback)
    if tid is not None:
        b.SetThreadID(tid)
    BP.add(b.GetID())
    return b.GetID()


def ensure(frame):
    module = frame.GetModule()
    target = frame.GetThread().GetProcess().GetTarget()
    path = Path(str(module.GetFileSpec()))
    key = (str(path), module.GetObjectFileHeaderAddress().GetLoadAddress(target))
    if key in MODULES:
        return
    if not target.GetTriple().startswith('x86_64'):
        raise ValueError('Only x86_64 ABI is audited')
    if fmt.digest(path.read_bytes()) != fmt.ADAPTER_SHA256:
        raise ValueError('Adapter hash mismatch; offsets NOT applied')
    if module.GetUUIDString().replace('-', '').lower() != '6fc99e910efe326eb2841fde610d1697':
        raise ValueError('Loaded module UUID differs from audited on-disk adapter')
    for site in SITES:
        address = module.ResolveFileAddress(site).GetLoadAddress(target)
        if address == lldb.LLDB_INVALID_ADDRESS:
            raise ValueError('Cannot resolve adapter offset')
        add_bp(target, address, 'branch')
    MODULES.add(key)


def ret_bp(frame, record):
    thread = frame.GetThread()
    process = thread.GetProcess()
    sp = reg(frame, 'rsp')
    key = (thread.GetThreadID(), sp + 8)
    if key in RET:
        raise ValueError('Overlapping return breakpoint')
    record['bp'] = add_bp(process.GetTarget(), word(process, sp), 'returned', key[0])
    RET[key] = record


def fail(exc):
    # Stop on capture failure: operator can detach; never pretend a dump succeeded.
    print('xe capture stopped: ' + str(exc))
    return True


def created(frame, bp_loc, _dict):
    try:
        ensure(frame)
        if frame.GetPCAddress().GetFileAddress() != 0x600:
            raise ValueError('Create breakpoint skipped prologue')
        process = frame.GetThread().GetProcess()
        hw = memory(process, reg(frame, 'rdi'), 0x80)
        ret_bp(frame, {'kind': 'create', 'hw': hw})
        return False
    except Exception as exc:
        return fail(exc)


def entered(frame, bp_loc, _dict):
    global COUNT
    try:
        ensure(frame)
        if frame.GetPCAddress().GetFileAddress() != 0x12c0:
            raise ValueError('Build breakpoint skipped prologue')
        if COUNT >= LIMIT:
            raise ValueError('64 request limit reached; xe-disarm then process detach')
        process = frame.GetThread().GetProcess()
        tid = frame.GetThread().GetThreadID()
        if tid in ACTIVE:
            raise ValueError('Nested build is not supported')
        compiler, request, size, flags, bc, length = [reg(frame, r) for r in
                                                    ('rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9')]
        flags &= 0xffffffff
        COUNT += 1
        folder = ROOT / ('request-%04d' % COUNT)
        folder.mkdir(mode=0o700)
        meta = {'schema': 1, 'adapter_sha256': fmt.ADAPTER_SHA256,
                'request_size': size, 'flags': flags, 'bitcode_size': length,
                'hw': None, 'rejections': [], 'observations': [], 'result': None, 'errors': []}
        # Save metadata first, including incomplete/missing captures.
        save(folder, meta)
        try:
            meta['request'] = fmt.blob(folder, 'request', memory(process, request, size))
            meta['bitcode'] = fmt.blob(folder, 'bitcode', memory(process, bc, length))
            meta['layout'] = fmt.layout((folder / 'bitcode.bin').read_bytes())
            if compiler in HW:
                meta['hw'] = fmt.blob(folder, 'hw', HW[compiler])
        except Exception as exc:
            meta['errors'].append(str(exc))
        slots = struct.unpack('<7Q', memory(process, reg(frame, 'rsp') + 8, 56))
        record = {'kind': 'build', 'folder': folder, 'meta': meta, 'slots': slots}
        ret_bp(frame, record)
        ACTIVE[tid] = record
        save(folder, meta)
        return False
    except Exception as exc:
        return fail(exc)


def branch(frame, bp_loc, _dict):
    try:
        record = ACTIVE.get(frame.GetThread().GetThreadID())
        if record:
            pc = frame.GetPCAddress().GetFileAddress()
            kind, reason = SITES[pc]
            flags = reg(frame, 'rflags')
            if pc in (0x1552, 0x159a):
                record['meta']['observations'].append({'site': hex(pc), 'eax': reg(frame, 'rax') & 0xffffffff})
            elif pc == 0x1575:
                record['meta']['observations'].append({'site': hex(pc), 'ebx': reg(frame, 'rbx') & 0xffffffff})
            if taken(kind, flags):
                record['meta']['rejections'].append({'site': hex(pc), 'reason': reason})
                save(record['folder'], record['meta'])
        return False
    except Exception as exc:
        return fail(exc)


def returned(frame, bp_loc, _dict):
    try:
        tid = frame.GetThread().GetThreadID()
        key = (tid, reg(frame, 'rsp'))
        record = RET.get(key)
        # Same return PC can occur in another call on this thread; don't consume it.
        if not record or record['bp'] != bp_loc.GetBreakpoint().GetID():
            return False
        RET.pop(key)
        process = frame.GetThread().GetProcess()
        process.GetTarget().BreakpointDelete(record['bp'])
        BP.discard(record['bp'])
        if record['kind'] == 'create':
            HW[reg(frame, 'rax')] = record['hw']
        else:
            ACTIVE.pop(tid, None)
            meta = record['meta']
            meta['result'] = reg(frame, 'rax') & 0xffffffff
            try:
                meta['output_words'] = [word(process, p) for p in record['slots']]
                errptr = meta['output_words'][6]
                if errptr:
                    err = lldb.SBError()
                    meta['error_text'] = process.ReadCStringFromMemory(errptr, 512, err)
                    if err.Fail():
                        meta['errors'].append('Error string unavailable')
            except Exception as exc:
                meta['errors'].append(str(exc))
            save(record['folder'], meta)
            print('xe captured %s result=%d' % (record['folder'].name, meta['result']))
        return False
    except Exception as exc:
        return fail(exc)


def arm(debugger, command, result, _dict):
    global ROOT
    try:
        if ROOT is not None:
            raise ValueError('Already armed; restart LLDB for another session')
        args = shlex.split(command)
        if len(args) != 1:
            raise ValueError('Usage: xe-arm /absolute/private/new-directory')
        root = Path(args[0]).expanduser()
        if not root.is_absolute():
            raise ValueError('Capture directory must be absolute')
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
        ROOT = root
        target = debugger.GetSelectedTarget()
        for name, callback in [('MTLCompilerCreate', 'created'),
                               ('MTLCompilerBuildRequestWithSerializedBitcode', 'entered')]:
            reply = lldb.SBCommandReturnObject()
            debugger.GetCommandInterpreter().HandleCommand(
                'breakpoint set -n %s -s adapter.dylib -K false' % name, reply)
            if not reply.Succeeded():
                raise ValueError(reply.GetError())
            bp = target.GetBreakpointAtIndex(target.GetNumBreakpoints() - 1)
            bp.SetScriptCallbackFunction(__name__ + '.' + callback)
            BP.add(bp.GetID())
        result.PutCString('Armed pending/exact entry breakpoints. continue; detach to end. Private captures only.')
    except Exception as exc:
        result.SetError(str(exc))


def disarm(debugger, command, result, _dict):
    target = debugger.GetSelectedTarget()
    for ident in list(BP):
        target.BreakpointDelete(ident)
    BP.clear()
    RET.clear()
    ACTIVE.clear()
    result.PutCString('Capture breakpoints removed. process detach')


def __lldb_init_module(debugger, _dict):
    debugger.HandleCommand('command script add -f %s.arm xe-arm' % __name__)
    debugger.HandleCommand('command script add -f %s.disarm xe-disarm' % __name__)

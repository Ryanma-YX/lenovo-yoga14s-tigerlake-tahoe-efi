/* Native macOS JXA disk guard. No disk mutations; pure validation is CPU-testable. */
function norm(x) { return String(x || '').replace(/[{}-]/g, '').toLowerCase(); }
function requireThat(ok, why) { if (!ok) throw new Error(why); }
function bytes(x) { return Number(x.TotalSize || x.Size || 0); }
function uuid(x) { return norm(x.DiskUUID || x.PartitionUUID); }
function offset(x) { return Number(x.PartitionMapPartitionOffset !== undefined ? x.PartitionMapPartitionOffset : x.PartitionOffset); }
function findPartitionDisks(plan, disks) {
    var specs = [plan.esp];
    if (plan.protected) specs.push(plan.protected, plan.target);
    return disks.filter(function (d) {
        return specs.every(function (s) {
            var hits = d.parts.filter(function (p) { return uuid(p) === norm(s.guid); });
            return hits.length === 1 && hits[0].ParentWholeDisk === d.whole.DeviceIdentifier;
        });
    });
}
function validateUSB(plan, snapshot, sskDisk) {
    var w = snapshot.whole, parts = snapshot.parts;
    requireThat(w.Internal === false && bytes(w) === plan.disk.bytes, 'USB capacity/external identity changed');
    requireThat(/^disk\d+$/.test(w.DeviceIdentifier) && w.DeviceIdentifier !== sskDisk, 'USB must be separate from installation SSD');
    requireThat(parts.length === 2, 'USB partition count changed');
    function match(spec, checkUUID) {
        var hits = parts.filter(function (p) {
            return offset(p) === spec.offset && bytes(p) === spec.bytes &&
                (!checkUUID || uuid(p) === norm(spec.guid));
        });
        requireThat(hits.length === 1 && hits[0].ParentWholeDisk === w.DeviceIdentifier &&
            /^disk\d+s\d+$/.test(hits[0].DeviceIdentifier), 'USB partition identity/layout changed');
        return hits[0];
    }
    var esp = match(plan.esp, true), media = match(plan.media, false);
    requireThat(bytes(media) >= 32 * 1073741824, 'USB installer partition too small');
    requireThat(esp.Content === 'EFI', 'USB EFI partition type changed');
    return {usbWholeDisk:w.DeviceIdentifier, usbEsp:esp.DeviceIdentifier, usbMedia:media.DeviceIdentifier,
        usbMount:media.MountPoint || null};
}
function findSerialDisks(nodes, wanted) {
    var found = [];
    function walk(node, inherited) {
        var serial = node['USB Serial Number'] || node['Serial Number'] || node.kUSBSerialNumberString || inherited;
        var bsd = node['BSD Name'];
        if (String(serial || '').trim() === wanted && /^disk\d+$/.test(String(bsd))) found.push(bsd);
        (node.IORegistryEntryChildren || []).forEach(function (child) { walk(child, serial); });
    }
    nodes.forEach(function (n) { walk(n, ''); });
    return found.filter(function (v, i, a) { return a.indexOf(v) === i; });
}
function validate(plan, snapshot, mode) {
    var whole = snapshot.whole, parts = snapshot.parts;
    requireThat(whole.Internal === false, 'Identified disk is not explicitly external');
    requireThat(bytes(whole) === plan.disk.bytes, 'External SSD capacity changed');
    requireThat(/^disk\d+$/.test(whole.DeviceIdentifier), 'Invalid whole-disk identifier');
    if (snapshot.identityMethod === 'gpt-layout') {
        requireThat(findPartitionDisks(plan, snapshot.candidates || []).length === 1 &&
            findPartitionDisks(plan, snapshot.candidates)[0].whole.DeviceIdentifier === whole.DeviceIdentifier,
            'GPT partition identity is missing or ambiguous');
        requireThat(snapshot.serialDisks.length <= 1 && (!snapshot.serialDisks.length || snapshot.serialDisks[0] === whole.DeviceIdentifier),
            'USB serial conflicts with GPT identity');
    } else {
        requireThat(snapshot.serialDisks.length === 1 && snapshot.serialDisks[0] === whole.DeviceIdentifier,
                    'USB serial is missing, ambiguous, or belongs to another disk');
    }
    function matching(spec) {
        var matches = parts.filter(function (p) { return uuid(p) === norm(spec.guid); });
        requireThat(matches.length === 1, 'Partition UUID missing or duplicated');
        var part = matches[0];
        requireThat(offset(part) === spec.offset, 'Partition start changed');
        requireThat(part.ParentWholeDisk === whole.DeviceIdentifier, 'Partition belongs to another disk');
        requireThat(/^disk\d+s\d+$/.test(part.DeviceIdentifier), 'Invalid physical partition identifier');
        return part;
    }
    var protectedPart = matching(plan.protected), esp = matching(plan.esp), target = matching(plan.target);
    requireThat(bytes(protectedPart) === plan.protected.bytes, 'Protected APFS partition size changed');
    requireThat(bytes(esp) === plan.esp.bytes, 'EFI partition size changed');
    var newSize = Math.floor((plan.target.bytes - plan.installerReserveBytes) / 1048576) * 1048576;
    var installer = null;
    if (mode === 'initial' || mode === 'external-media' || mode === 'external-recovery') {
        requireThat(bytes(target) === plan.target.bytes, 'Tahoe region no longer has its original size');
    } else if (mode === 'resized' || mode === 'resized-recovery') {
        requireThat(Math.abs(bytes(target) - newSize) <= 16 * 1048576, 'Unexpected resized target size');
        var possible = parts.filter(function (p) {
            var start = offset(p), end = start + bytes(p);
            return start >= plan.target.offset + bytes(target) &&
                   end <= plan.target.offset + plan.target.bytes && bytes(p) >= 30 * 1073741824;
        });
        requireThat(possible.length === 1, 'Temporary installer partition is missing or ambiguous');
        installer = possible[0];
        requireThat(installer.Content === 'Apple_HFS', 'Temporary installer must be an HFS partition');
    } else {
        throw new Error('Unknown guard mode');
    }
    var containers = snapshot.apfs.Containers || [];
    var selected = containers.filter(function (c) {
        var stores = c.PhysicalStores || [];
        return stores.length === 1 && stores[0].DeviceIdentifier === target.DeviceIdentifier;
    });
    requireThat(selected.length === 1, 'Target APFS container is missing, shared, or ambiguous');
    var container = selected[0];
    var rootContainer = snapshot.root.APFSContainerReference || snapshot.root.ParentWholeDisk;
    if (mode !== 'resized-recovery' && mode !== 'external-recovery') {
        requireThat(rootContainer === container.ContainerReference, 'Current macOS is not on the approved Tahoe region');
    }
    requireThat((container.Volumes || []).every(function (v) { return !v.Locked; }), 'Target APFS contains locked volumes');
    if (mode === 'initial') {
        requireThat(Number(container.CapacityFree !== undefined ? container.CapacityFree : container.CapacityNotAllocated) >= 64 * 1073741824,
                    'Need at least 64 GiB free in Tahoe container before staging the installer');
    }
    var result = {schema: 1, mode: mode, wholeDisk: whole.DeviceIdentifier,
            targetStore: target.DeviceIdentifier, targetContainer: container.ContainerReference,
            esp: esp.DeviceIdentifier, protectedStore: protectedPart.DeviceIdentifier,
            resizedTargetBytes: newSize, installerDevice: installer ? installer.DeviceIdentifier : null,
            installerMount: installer ? installer.MountPoint : null,
            installerUUID: installer ? (installer.DiskUUID || installer.PartitionUUID) : null,
            protectedPartitionUnchanged: true, identityMethod:snapshot.identityMethod || 'usb-serial'};
    if (mode === 'external-media' || mode === 'external-recovery') {
        requireThat(Boolean(plan.usb && snapshot.usb), 'Approved separate USB identity is required');
        var usb = validateUSB(plan.usb, snapshot.usb, whole.DeviceIdentifier);
        Object.keys(usb).forEach(function (key) { result[key] = usb[key]; });
    }
    return result;
}
function run(argv) {
    ObjC.import('Foundation');
    var app = Application.currentApplication(); app.includeStandardAdditions = true;
    function read(path) {
        var data = $.NSData.dataWithContentsOfFile(path);
        requireThat(Boolean(data), 'Cannot read input file');
        return $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding).js;
    }
    function plist(command) {
        var text = app.doShellScript(command);
        var data = $.NSString.alloc.initWithUTF8String(text).dataUsingEncoding($.NSUTF8StringEncoding);
        return ObjC.deepUnwrap($.NSPropertyListSerialization.propertyListWithDataOptionsFormatError(data, 0, null, null));
    }
    requireThat(argv.length === 3, 'Usage: plan.json output.json initial|resized');
    var plan = JSON.parse(read(argv[0])), mode = argv[2];
    // Windows storage serials need not equal USB bridge serials on macOS.
    // Select by the unique combination of saved GPT partition UUIDs instead.
    // Capacity, offsets, sizes, parent disk and APFS store are still mandatory.
    var serialDisks = [];
    try { serialDisks = findSerialDisks(plist('/usr/sbin/ioreg -a -r -c IOUSBHostDevice'), plan.disk.serial); } catch (e) {}
    var listed = plist('/usr/sbin/diskutil list -plist');
    var candidates = (listed.AllDisksAndPartitions || []).filter(function (d) {
        return /^disk\d+$/.test(d.DeviceIdentifier) && (d.Partitions || []).length > 0;
    }).map(function (d) {
        return {whole:plist('/usr/sbin/diskutil info -plist /dev/' + d.DeviceIdentifier),
            parts:d.Partitions.map(function (p) {
                requireThat(/^disk\d+s\d+$/.test(p.DeviceIdentifier), 'Invalid partition identifier');
                return plist('/usr/sbin/diskutil info -plist /dev/' + p.DeviceIdentifier);
            })};
    });
    var matched = findPartitionDisks(plan, candidates);
    requireThat(matched.length === 1, 'Cannot associate unique saved GPT partition UUIDs with a physical disk');
    var snapshot = {whole: matched[0].whole, parts: matched[0].parts, serialDisks: serialDisks,
                    identityMethod:'gpt-layout', candidates:candidates,
                    apfs: plist('/usr/sbin/diskutil apfs list -plist'),
                    root: plist('/usr/sbin/diskutil info -plist /')};
    if (mode === 'external-media' || mode === 'external-recovery') {
        requireThat(Boolean(plan.usb), 'Separate USB plan is missing');
        var usbMatched = findPartitionDisks(plan.usb, candidates);
        requireThat(usbMatched.length === 1, 'Cannot associate unique USB EFI UUID with a physical disk');
        snapshot.usb = usbMatched[0];
    }
    var state = validate(plan, snapshot, mode);
    var output = $.NSString.alloc.initWithUTF8String(JSON.stringify(state, null, 2));
    requireThat(output.writeToFileAtomicallyEncodingError(argv[1], true, $.NSUTF8StringEncoding, null), 'Cannot save guard result');
    return 'External SSD identity and protected-partition checks passed.';
}
if (typeof module !== 'undefined') module.exports = {validate: validate, findSerialDisks: findSerialDisks,
    findPartitionDisks:findPartitionDisks, validateUSB:validateUSB};

/* Native macOS JXA disk guard. No disk mutations; pure validation is CPU-testable. */
function norm(x) { return String(x || '').replace(/[{}-]/g, '').toLowerCase(); }
function requireThat(ok, why) { if (!ok) throw new Error(why); }
function bytes(x) { return Number(x.TotalSize || x.Size || 0); }
function uuid(x) { return norm(x.DiskUUID || x.PartitionUUID); }
function offset(x) { return Number(x.PartitionOffset); }
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
    requireThat(snapshot.serialDisks.length === 1 && snapshot.serialDisks[0] === whole.DeviceIdentifier,
                'USB serial is missing, ambiguous, or belongs to another disk');
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
    if (mode === 'initial') {
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
    if (mode !== 'resized-recovery') {
        requireThat(rootContainer === container.ContainerReference, 'Current macOS is not on the approved Tahoe region');
    }
    requireThat((container.Volumes || []).every(function (v) { return !v.Locked; }), 'Target APFS contains locked volumes');
    if (mode === 'initial') {
        requireThat(Number(container.CapacityNotAllocated) >= 64 * 1073741824,
                    'Need at least 64 GiB free in Tahoe container before staging the installer');
    }
    return {schema: 1, mode: mode, wholeDisk: whole.DeviceIdentifier,
            targetStore: target.DeviceIdentifier, targetContainer: container.ContainerReference,
            esp: esp.DeviceIdentifier, protectedStore: protectedPart.DeviceIdentifier,
            resizedTargetBytes: newSize, installerDevice: installer ? installer.DeviceIdentifier : null,
            installerMount: installer ? installer.MountPoint : null,
            installerUUID: installer ? (installer.DiskUUID || installer.PartitionUUID) : null,
            protectedPartitionUnchanged: true};
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
    var registry = plist('/usr/sbin/ioreg -a -r -c IOUSBHostDevice');
    var serialDisks = findSerialDisks(registry, plan.disk.serial);
    requireThat(serialDisks.length === 1, 'Cannot associate unique USB serial with an IOMedia disk');
    var disk = serialDisks[0];
    requireThat(/^disk\d+$/.test(disk), 'Invalid BSD disk name');
    var whole = plist('/usr/sbin/diskutil info -plist /dev/' + disk);
    var listed = plist('/usr/sbin/diskutil list -plist /dev/' + disk);
    var list = listed.AllDisksAndPartitions || [];
    requireThat(list.length === 1, 'Whole-disk listing is ambiguous');
    var parts = (list[0].Partitions || []).map(function (p) {
        requireThat(/^disk\d+s\d+$/.test(p.DeviceIdentifier), 'Invalid partition identifier');
        return plist('/usr/sbin/diskutil info -plist /dev/' + p.DeviceIdentifier);
    });
    var snapshot = {whole: whole, parts: parts, serialDisks: serialDisks,
                    apfs: plist('/usr/sbin/diskutil apfs list -plist'),
                    root: plist('/usr/sbin/diskutil info -plist /')};
    var state = validate(plan, snapshot, mode);
    var output = $.NSString.alloc.initWithUTF8String(JSON.stringify(state, null, 2));
    requireThat(output.writeToFileAtomicallyEncodingError(argv[1], true, $.NSUTF8StringEncoding, null), 'Cannot save guard result');
    return 'External SSD identity and protected-partition checks passed.';
}
if (typeof module !== 'undefined') module.exports = {validate: validate, findSerialDisks: findSerialDisks};

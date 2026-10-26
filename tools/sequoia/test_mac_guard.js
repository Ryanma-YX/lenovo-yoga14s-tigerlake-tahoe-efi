const assert = require('node:assert/strict');
const {validate, findSerialDisks} = require('./mac_disk_guard.js');
const GiB = 1073741824;
const plan = {disk:{serial:'TEST-SSD',bytes:512*GiB},
  esp:{guid:'aaaaaaaa-1111-1111-1111-111111111111',offset:1048576,bytes:256*1048576},
  protected:{guid:'bbbbbbbb-2222-2222-2222-222222222222',offset:GiB,bytes:256*GiB},
  target:{guid:'cccccccc-3333-3333-3333-333333333333',offset:257*GiB,bytes:255*GiB},
  installerReserveBytes:32*GiB};
function part(spec,id) {return {DiskUUID:spec.guid,PartitionOffset:spec.offset,TotalSize:spec.bytes,ParentWholeDisk:'disk7',DeviceIdentifier:id};}
const good = {whole:{Internal:false,TotalSize:plan.disk.bytes,DeviceIdentifier:'disk7'},
  serialDisks:['disk7'],parts:[part(plan.esp,'disk7s1'),part(plan.protected,'disk7s3'),part(plan.target,'disk7s4')],
  root:{APFSContainerReference:'disk9'},apfs:{Containers:[{ContainerReference:'disk9',CapacityNotAllocated:140*GiB,
    PhysicalStores:[{DeviceIdentifier:'disk7s4'}],Volumes:[{Locked:false}]}]}};
assert.equal(validate(plan,good,'initial').targetStore,'disk7s4');
let checks=1;
for (const mutate of [
  x=>x.whole.Internal=true,
  x=>x.whole.TotalSize--,
  x=>x.serialDisks=['disk0'],
  x=>x.serialDisks.push('disk8'),
  x=>x.parts[1].TotalSize--,
  x=>x.parts[1].PartitionOffset++,
  x=>x.parts[2].DiskUUID=plan.protected.guid,
  x=>x.parts[2].ParentWholeDisk='disk0',
  x=>x.root.APFSContainerReference='disk2',
  x=>x.apfs.Containers[0].PhysicalStores.push({DeviceIdentifier:'disk0s2'}),
  x=>x.apfs.Containers[0].CapacityNotAllocated=40*GiB,
  x=>x.apfs.Containers[0].Volumes[0].Locked=true
]) {const x=structuredClone(good);mutate(x);assert.throws(()=>validate(plan,x,'initial'));checks++;}
const resized=structuredClone(good);
resized.parts[2].TotalSize=Math.floor((plan.target.bytes-plan.installerReserveBytes)/1048576)*1048576;
resized.parts.push({DiskUUID:'dddddddd-4444-4444-4444-444444444444',PartitionOffset:plan.target.offset+resized.parts[2].TotalSize+1048576,
  TotalSize:31*GiB,Content:'Apple_HFS',DeviceIdentifier:'disk7s5',ParentWholeDisk:'disk7',MountPoint:'/Volumes/SEQ-INSTALL'});
assert.equal(validate(plan,resized,'resized').installerDevice,'disk7s5');checks++;
const recovery=structuredClone(resized);recovery.root.APFSContainerReference='disk20';
assert.equal(validate(plan,recovery,'resized-recovery').targetStore,'disk7s4');checks++;
assert.throws(()=>validate(plan,recovery,'resized'));checks++;
resized.parts[3].PartitionOffset=plan.protected.offset;
assert.throws(()=>validate(plan,resized,'resized'));checks++;
assert.deepEqual(findSerialDisks([{'USB Serial Number':'TEST-SSD',IORegistryEntryChildren:[{'BSD Name':'disk7'}]}],'TEST-SSD'),['disk7']);checks++;
console.log(JSON.stringify({stage:'pure-JavaScript-fixtures',passed:checks,nativeJXATested:false,macosDiskMutationTested:false}));

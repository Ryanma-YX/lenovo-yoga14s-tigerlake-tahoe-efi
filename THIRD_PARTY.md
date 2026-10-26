# Third-party components

This repository is a configuration archive, not an original implementation of the bundled bootloader or drivers. No single repository-wide license is asserted over third-party binaries.

Each component remains subject to its upstream copyright and license. Available notices are retained in `licenses/`; the fetched notice locations are recorded in `docs/license-sources.json`. Exact downloaded package URLs and checksums are recorded in `docs/component-sources.json`. The configuration patch retains OpCore-Simplify's BSD 3-Clause notice.

| Component | Upstream |
| --- | --- |
| OpenCore / OpenRuntime / ResetNvramEntry / ocvalidate | https://github.com/acidanthera/OpenCorePkg |
| HfsPlus / external APFS EFI driver | https://github.com/acidanthera/OcBinaryData |
| Lilu | https://github.com/acidanthera/Lilu |
| VirtualSMC and plugins | https://github.com/acidanthera/VirtualSMC |
| WhateverXe | https://github.com/b00t0x/WhateverXe |
| AMFIPass Mod distribution | https://github.com/b00t0x/WhateverXe-Graphics |
| AppleALC | https://github.com/acidanthera/AppleALC |
| AirportItlwm Tahoe / Sequoia builds | https://github.com/laobamac/itlwm |
| SimpleHDA | https://github.com/laobamac/SimpleHDA |
| BlueToolFixup | https://github.com/acidanthera/BrcmPatchRAM |
| Intel Bluetooth drivers | https://github.com/OpenIntelWireless/IntelBluetoothFirmware |
| USBToolBox / UTBDefault | https://github.com/USBToolBox/kext |
| XHCI-unsupported | https://github.com/RehabMan/OS-X-USB-Inject-All |
| VoodooPS2Controller | https://github.com/acidanthera/VoodooPS2 |
| VoodooI2C / VoodooI2CHID / plugins | https://github.com/VoodooI2C/VoodooI2C |
| YogaSMC | https://github.com/zhen-zen/YogaSMC |
| NVMeFix | https://github.com/acidanthera/NVMeFix |
| RestrictEvents | https://github.com/acidanthera/RestrictEvents |
| BrightnessKeys | https://github.com/acidanthera/BrightnessKeys |
| ECEnabler | https://github.com/1Revenger1/ECEnabler |
| OpCore-Simplify patch baseline | https://github.com/lzhoang2801/OpCore-Simplify |

Some upstream projects use copyleft licenses. Their linked source repositories and exact revisions, where available, are part of the component provenance. Package inclusion does not imply that licenses from unrelated projects apply to those files.

Apple recovery images and the WhateverXe Graphics installer payload are not redistributed here. This repository does not bundle firmware dumps, Windows recovery data, disk images or machine-specific raw diagnostic reports.

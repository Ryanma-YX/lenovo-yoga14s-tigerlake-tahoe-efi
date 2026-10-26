# Sequoia video acceleration isolation

These are local diagnostic tools for the signed WhateverXe Graphics 0.2.0 Sequoia payload. They do not install drivers or change EFI, SMBIOS, Apple Account credentials or SIP.

## Preserve 3D while isolating VA

On the installed Intel Sequoia 15.8.x system:

```bash
bash tools/graphics/Video-Acceleration.command status
bash tools/graphics/Video-Acceleration.command disable
```

The second command requests sudo, verifies all five VA payload files against `va-files.sha256`, and moves the whole `AppleIntelTGLGraphicsVADriver.bundle` outside `/Library/GPUBundles`. The Metal plugin stays in place. Restart, boot the accelerated EFI and test the affected application.

This is an experiment affecting hardware video decoding **and encoding**. Software fallback or successful playback is not guaranteed. On this laptop, the owner reported that App Store stopped freezing after isolation while 3D remained enabled. It does not establish that all GPU workloads are stable.

To restore the exact saved bundle, run and restart:

```bash
bash tools/graphics/Video-Acceleration.command restore
```

The backup is under `/Library/Application Support/WhateverXe-Video-Test-20261026`. The date is retained to stay compatible with the deployed experiment. No signed files are edited or re-signed, no System files are modified, and no AuxKC rebuild is required for this user-space plugin move. Existing clients can retain the loaded plugin until restart. If both the live and saved bundle exist, the script stops rather than overwriting either one.

The manifest is stored with LF endings. The verifier also strips CR before checking, fixing the earlier Windows CRLF filename error without bypassing hashes.

## Collect previous freeze and account diagnostics

```bash
bash tools/graphics/Collect-AppStore.command 2h
```

Reports go to the user's Desktop. When run from a mounted volume, reports smaller than 24 MiB are also copied beside the script in `Reports/`. Larger reports remain on Desktop. Keep reports local: they can contain machine, account or network identifiers.

The collector includes GPU/WindowServer, App Store, account services, VideoToolbox and VA logs, recent crash reports, versions and network-interface metadata. It accepts `30m`, `2h`, or another positive duration in minutes/hours/days. Unlike the first deployed collector, it retains the entire selected unified-log interval rather than only its last 10,000 lines. Force shutdown can still lose the last unflushed events.

Neither script launches App Store, triggers a freeze, restarts the machine or posts logs anywhere.

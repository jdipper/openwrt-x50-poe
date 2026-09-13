# Deco X50-PoE v2 boot and upgrade investigation

Tracking: https://github.com/jdipper/openwrt-x50-poe/issues/1

Baseline: `270b92ad80879fac9547f64e6cbce3680b654eec`.

This branch adds conservative upgrade checks. It does **not** fix or verify
first installation, slot selection, or persistent boot on hardware. It is not
a ready-to-flash release.

## Why the checks are necessary

Static inspection compared the experimental factory image linked from
https://github.com/ey3ball/openwrt/releases/tag/openwrt-x50-poe-v2-build1
with TP-Link's v2 stock firmware 1.0.1 (August 2023) and v2 GPL package:

- https://static.tp-link.com/upload/firmware/2023/202309/20230901/X50_PoE_V2_1.0.1_Build_20230807_Rel.52367.zip
- https://static.tp-link.com/upload/gpl-code/2023/202308/20230803/Deco_X50-POEv2_BASE_AX3000_GPL.tar.gz

Stock firmware contains static UBI volumes `uboot`, `kernel`, and `rootfs`.
The experimental factory image instead contains dynamic volumes `kernel`,
`rootfs`, and `rootfs_data`. The GPL bootloader binary contains both a
`volume uboot read error` message and a fallback-to-other-slot message.
The missing volume is a plausible cause of fallback, not a confirmed diagnosis.

The stock UBI loader is U-Boot 2022.07-rc3 (August 2023); the GPL second-stage
binary is U-Boot 2022.04-rc1 (January 2023). Do not assume interchangeability.
No matching source control flow or boot-success handshake has been established.

## Changes on this branch

- Only the sysupgrade image is advertised by the device profile. Factory
  image generation is removed because it supplies no vendor loader. Recovery
  initramfs generation remains available for investigation.
- Preflight and the ramfs upgrade stage both require an uncompressed sysupgrade
  tar with the expected board directory and nonempty CONTROL, kernel and root
  members. Raw UBI/FIT/UBIFS input is rejected by this board's path.
- Both stages require the MTD partition named `ubi0` to be attached and contain
  a volume named `uboot`. The UBI device number is discovered dynamically; it
  is not assumed to be `ubi0`. The check performs no attach or format operation.
- The generic tar upgrade replaces kernel/rootfs/rootfs_data by name and leaves
  the existing loader volume alone. Tests cover this behaviour. The guard avoids
  invoking generic NAND formatting fallback for an already-unattached slot;
  it does not make NAND writes atomic or protect against hardware failure.
- The factory partition is read-only, matching the already read-only
  factory_data and backup-slot partitions.
- runtime_data ends at `0x7200000`, matching the vendor DTS's 17 MiB partition
  at `0x6100000`, instead of claiming the remaining 31 MiB of the flash.

The guard intentionally rejects installations with no `uboot` volume, including
any potentially working direct-kernel boot setup. That conservative restriction
must be revisited when a supported boot path is verified. A present volume does
not prove that its contents are valid or compatible, or that the bootloader will
select slot 0. The guard is not a complete installation compatibility test.

No environment writes, alternate-slot writes, loader insertion, or load-address
changes are introduced. The existing 512 MiB RAM declaration remains pending
verification against the actual revision; an older vendor DTS declares 256 MiB.

## Evidence needed for the actual boot fix

1. Record the hardware revision, stock firmware version, complete serial
   cold-boot log, bootloader versions and read-only environment.
2. Identify both slots' volume lists and the first failing boot operation.
   Preserve backups before any write experiment.
3. Trace the matching loader's selection of `uboot`, kernel and slot. Establish
   whether it uses names or IDs and whether volume type matters.
4. Choose and test preservation of a compatible vendor second stage or a
   direct-kernel path. Derive any environment layout from evidence before
   adding envtools configuration or changing `tp_boot_idx`.
5. Parse the exact recovery FIT and calculate transport, decompression and DTB
   ranges. Transport load address and kernel entry point are different concepts.
6. Verify first install, repeated cold starts, later sysupgrade, fallback,
   Ethernet, calibration and MAC-address behaviour on hardware.

Do not close issue #1 on the basis of these host-side checks.

## Host-side validation

From the repository root:

```
python3 scripts/tests/test_deco_x50_poe_v2_upgrade.py
sh -n target/linux/mediatek/filogic/base-files/lib/upgrade/platform.sh
git diff --check
```

The regression suite sources the actual platform and NAND shell functions,
uses temporary tar fixtures, and mocks device access and flash commands. It
checks early and late rejection, dynamic UBI numbering, and loader-volume
preservation. It runs under host Bash, not target BusyBox ash. It does not
replace a firmware build, DTS compilation, target-shell tests or hardware tests.

Image SHA-256 fingerprints:

```
Stock container:   25e979f396090199fe60885c11eb18824f6829f8e8eef336fe3c409c87c855d6
OpenWrt container: 55cd78cd547bac24f248a4de42909fd7c16cfea15be9d7e9023f2c4801615614
Stock UBI uboot:   6704d010db8e9294867b5155eeeccfb0109ad19e93027d17f29b01cbbd0ec717
```

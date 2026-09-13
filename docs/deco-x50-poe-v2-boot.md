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

## GPL-package verification (2026-09-13)

Downloaded and inspected the v2 GPL release directly (`Deco_X50-POEv2_BASE_AX3000_GPL.tar.gz`,
same URL as above). It contains the actual production `uboot.bin` /
`second-uboot.bin` binaries and the product's reference DTS
(`build/product_configs/x50-poev2_1/mt7981-spim-nand-rfb.dts`), not just the
OpenWrt-side GPL sources.

Confirmed against the real firmware (no longer just plausible inference):

- RAM is 256 MiB (`reg = <0 0x40000000 0 0x10000000>`), not 512 MiB. Fixed in
  this branch.
- The vendor bootloader (`strings uboot.bin`) contains the literal message
  `volume uboot read error %d` plus the bare volume-name tokens `uboot`,
  `kernel`, `rootfs`, `rootfs_data`. The "uboot" UBI volume requirement is a
  fact about the real bootloader, not a conservative guess.
- The embedded `mtdparts=` kernel cmdline in `uboot.bin` matches this
  branch's partition table exactly, including `runtime_data` at 17 MiB
  (`0x01100000`) — the resize in this branch's DTS change is correct as
  measured against production firmware, not just "the vendor DTS."
- `second-uboot.bin` (a separate `u-boot legacy uImage`, type `seconduboot`)
  confirms a distinct second-stage loader binary exists in the real boot
  chain, consistent with the "vendor's second-stage uboot volume" theory.

Still not resolved by the GPL release:

- The `ubi_factory_data` UBI volume name assumed in `09_mount_cfg_part` for
  the `factory_data` partition. U-Boot's boot chain never touches
  `factory_data`, so its binaries have no opinion on this. The release's
  `openwrt/` and `sdk/mtk798x/openwrt-21.02/` trees are a generic, dated
  MediaTek reference tree, not this product's actual rootfs/init scripts.
  This needs either the stock firmware's rootfs or a live device.

## What's permanent vs. what's scaffolding for testing

This branch mixes two different kinds of change. Do not treat them the same
way when deciding what to keep:

**Confirmed correct — keep regardless of what hardware testing finds:**

- `runtime_data` resized to 17 MiB and marked read-only, and `factory`
  marked read-only (`17ac90a`) — matches the real `mtdparts=` string exactly.
- RAM size corrected to 256 MiB (this change) — matches the vendor's own
  product DTS exactly.
- The `uboot` UBI-volume requirement in `tplink_deco_x50_poe_v2_check()` —
  matches a literal error string and volume-name tokens in the real
  bootloader binary. This is not a conservative guess to relax later; it is
  how the hardware behaves.

**Testing scaffolding — appropriate for now, but revisit once hardware
testing gives an answer, don't leave as permanent without reconsidering:**

- Withholding `factory.bin` (`2bc09aa`). Correct while the boot chain is
  unverified. Once a working install path is confirmed (e.g. a rebuilt
  factory image that actually contains a valid `uboot` volume), this should
  be revisited, not left disabled indefinitely by default. See the
  `tplink_deco-x50-poe-v2-uboot-test` device profile below, which is exactly
  that rebuilt image, offered as a separate opt-in profile rather than
  folded into `factory.bin` — it has not been confirmed to work.
- The upgrade guard's blanket refusal to act on an unattached/misconfigured
  slot. Right call while unverified; may need a documented override or a
  clearer failure message once real failure modes are understood on
  hardware, per the existing note above about rejecting a "potentially
  working direct-kernel boot setup."

**Still unverified — blocks calling this device supported:**

- The `ubi_factory_data` volume name (see above).
- Any first-boot install path actually completing on real hardware. No
  image built from this branch has been confirmed to boot.

## Experimental uboot-volume test image (Option A from issue 3)

`Device/tplink_deco-x50-poe-v2-uboot-test` in `filogic.mk` builds
`factory-experimental.bin`: the same image as the withheld `factory.bin`,
plus a `uboot` UBI volume at volume ID 0 (ahead of `kernel`=1, `rootfs`=2),
populated from `second-uboot.bin` in the v2 GPL release — matching the
stock volume-ID layout from issue 1's evidence table exactly.

This is a deliberately separate device profile, not a change to
`Device/tplink_deco-x50-poe-v2`. Building or selecting the normal device is
unaffected by any of this.

New package: `package/firmware/tplink-deco-x50-poe-v2-uboot` downloads the
GPL release and extracts `uboot/second-uboot.bin` into
`STAGING_DIR_IMAGE`. See its `Package/.../description` for the one thing
this does **not** resolve: `second-uboot.bin` is U-Boot 2022.04-rc1
(January 2023); the actual primary bootloader on retail v2 units is
2022.07-rc3 (August 2023). Nothing here confirms those are compatible —
this only tests the "restoring the missing volume is sufficient" half of
the hypothesis.

Safety property, not a guarantee of success: this only ever writes inside
the `ubi0` UBI container. It never touches `bl2` (the primary bootloader)
or `ubi1` (the other slot). If the primary bootloader still can't boot from
`ubi0` after this, the fallback path already implicated in issue 1 should
still return the device to stock — same symptom as already reported, not a
new failure mode. This has not been verified on hardware and should not be
treated as confirmed until it has.

Not verified by anything in this repository: this Makefile/device profile
has not been run through a full OpenWrt build in this environment. Build it
end-to-end before flashing anything.

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

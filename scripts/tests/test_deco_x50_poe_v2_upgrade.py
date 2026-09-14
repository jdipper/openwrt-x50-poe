#!/usr/bin/env python3
"""Host-side regression tests; all device access and flash commands are mocked."""
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLATFORM = ROOT / 'target/linux/mediatek/filogic/base-files/lib/upgrade/platform.sh'
NAND = ROOT / 'package/base-files/files/lib/upgrade/nand.sh'
BOARD = 'sysupgrade-tplink_deco-x50-poe-v2'


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        # Only omit the target's /lib/functions.sh import. Exercise the actual
        # generic NAND implementation with the storage helpers mocked below.
        self.nand = self.path / 'nand.sh'
        self.nand.write_text(NAND.read_text().replace('. /lib/functions.sh', ''))

    def archive(self, board=BOARD, missing=None, empty=None, extra=False):
        path = self.path / 'image.bin'
        with tarfile.open(path, 'w', format=tarfile.USTAR_FORMAT) as tar:
            directory = tarfile.TarInfo(board + '/')
            directory.type = tarfile.DIRTYPE
            tar.addfile(directory)
            for name in ('CONTROL', 'kernel', 'root'):
                if name == missing:
                    continue
                data = b'' if name == empty else b'test fixture\n'
                info = tarfile.TarInfo(board + '/' + name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            if extra:
                directory = tarfile.TarInfo('sysupgrade-other/')
                directory.type = tarfile.DIRTYPE
                tar.addfile(directory)
        return path

    def run_shell(self, image, action='platform_check_image "$IMAGE"',
                  attached=True, loader=True):
        env = dict(os.environ, PLATFORM=str(PLATFORM), NAND=str(self.nand),
                   IMAGE=str(image), ATTACHED=str(int(attached)),
                   LOADER=str(int(loader)))
        script = r'''
. "$NAND"
. "$PLATFORM"
board_name() { echo tplink,deco-x50-poe-v2; }
nand_find_ubi() {
    [ "$1" = ubi0 ] || return 1
    [ "$ATTACHED" = 1 ] && echo ubi7
}
nand_find_volume() {
    [ "$1" = ubi7 ] || return 1
    case "$2" in
        uboot) [ "$LOADER" = 1 ] && echo ubi7_0 ;;
        kernel) echo ubi7_1 ;;
        rootfs) echo ubi7_2 ;;
        rootfs_data) echo ubi7_3 ;;
    esac
}
nand_do_upgrade() { echo "UPGRADE:$CI_UBIPART:$CI_KERNPART:$CI_ROOTPART"; }
nand_do_upgrade_failed() { echo FAILED; return 1; }
ubiformat() { echo UNEXPECTED_FORMAT; return 99; }
ubiattach() { echo UNEXPECTED_ATTACH; return 99; }
'''
        return subprocess.run(['/bin/bash', '-c', script + '\n' + action],
                              env=env, text=True, capture_output=True)

    def test_valid_tar_and_attached_loader(self):
        result = self.run_shell(self.archive())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_metadata_trailer_is_accepted(self):
        image = self.archive()
        with image.open('ab') as out:
            out.write(b'fixture for appended image metadata')
        result = self.run_shell(image)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_and_empty_members(self):
        for member in ('CONTROL', 'kernel', 'root'):
            for option in ('missing', 'empty'):
                with self.subTest(member=member, option=option):
                    result = self.run_shell(self.archive(**{option: member}))
                    self.assertNotEqual(result.returncode, 0)

    def test_wrong_board_and_multiple_directories(self):
        for options in ({'board': 'sysupgrade-other'}, {'extra': True}):
            with self.subTest(options=options):
                self.assertNotEqual(self.run_shell(self.archive(**options)).returncode, 0)

    def test_raw_images_rejected_even_in_upgrade_stage(self):
        for magic in (b'UBI#', b'\xd0\x0d\xfe\xed', b'\x31\x18\x10\x06', b'fw-type:Cloud'):
            image = self.path / 'raw.bin'
            image.write_bytes(magic + bytes(1024))
            with self.subTest(magic=magic):
                result = self.run_shell(image, 'platform_do_upgrade "$IMAGE"')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('UPGRADE:', result.stdout)

    def test_storage_failures_rejected_in_both_stages(self):
        for action in ('platform_check_image "$IMAGE"', 'platform_do_upgrade "$IMAGE"'):
            for options in ({'attached': False}, {'loader': False}):
                with self.subTest(action=action, options=options):
                    result = self.run_shell(self.archive(), action, **options)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn('UPGRADE:', result.stdout)
                    self.assertNotIn('UNEXPECTED_', result.stdout)

    def test_valid_upgrade_uses_partition_name_not_ubi_device_number(self):
        result = self.run_shell(self.archive(), 'platform_do_upgrade "$IMAGE"')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('UPGRADE:ubi0:kernel:rootfs', result.stdout)

    def test_generic_tar_preparation_preserves_loader(self):
        action = r'''
fw_printenv() { return 1; }
nand_attach_ubi() { nand_find_ubi "$1"; }
nand_remove_ubiblock() { return 0; }
ubirmvol() { echo "REMOVE:$*"; }
ubimkvol() { echo "CREATE:$*"; }
CI_UBIPART=ubi0
nand_upgrade_prepare_ubi 4096 squashfs 4096 0
'''
        result = self.run_shell(self.archive(), action)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        removed = [line for line in result.stdout.splitlines() if line.startswith('REMOVE:')]
        self.assertEqual(removed, ['REMOVE:/dev/ubi7 -N kernel',
                                   'REMOVE:/dev/ubi7 -N rootfs',
                                   'REMOVE:/dev/ubi7 -N rootfs_data'])


if __name__ == '__main__':
    unittest.main()

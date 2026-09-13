include $(TOPDIR)/rules.mk

PKG_NAME:=tplink-deco-x50-poe-v2-uboot
PKG_VERSION:=2023-08-03
PKG_RELEASE:=1

PKG_SOURCE:=Deco_X50-POEv2_BASE_AX3000_GPL.tar.gz
PKG_SOURCE_URL:=https://static.tp-link.com/upload/gpl-code/2023/202308/20230803/
PKG_HASH:=254d2bf6a7429759ab3661b482692bbda37bd589f85199ca56f0f4e66b9d5677

PKG_LICENSE:=GPL-2.0-or-later
PKG_LICENSE_FILES:=

include $(INCLUDE_DIR)/package.mk

define Package/tplink-deco-x50-poe-v2-uboot
  SECTION:=firmware
  CATEGORY:=Firmware
  TITLE:=TP-Link Deco X50-PoE v2 vendor second-stage U-Boot (EXPERIMENTAL)
  DEPENDS:=@TARGET_mediatek_filogic
endef

define Package/tplink-deco-x50-poe-v2-uboot/description
  Extracts uboot/second-uboot.bin from TP-Link's v2 GPL release
  (X50-PoE v2, firmware 1.0.1, August 2023) for use as the "uboot" UBI
  volume in an experimental image for this device. See
  docs/deco-x50-poe-v2-boot.md.

  This binary (U-Boot 2022.04-rc1, January 2023) has not been confirmed
  compatible with the primary bootloader shipped on retail v2 units
  (U-Boot 2022.07-rc3, August 2023). Restoring this volume is a test of
  the leading boot-fallback hypothesis, not a confirmed fix. Untouched
  by this package: the device's primary bootloader (bl2) and the
  device's other UBI slot (ubi1) are never written by anything that
  consumes this package's output.
endef

# The upstream archive is a ~370 MiB vendor GPL dump; only one ~760 KiB
# file from it is needed here, so skip the default full-tree unpack.
UNPACK_CMD:=

define Build/Compile
	$(TAR) -C $(PKG_BUILD_DIR) -xzf $(DL_DIR)/$(PKG_SOURCE) \
		--strip-components=2 X50-POEv2_GPL/uboot/second-uboot.bin
endef

define Build/InstallDev
	$(INSTALL_DIR) $(STAGING_DIR_IMAGE)
	$(INSTALL_DATA) $(PKG_BUILD_DIR)/second-uboot.bin \
		$(STAGING_DIR_IMAGE)/mt7981_tplink_deco-x50-poe-v2-second-uboot.bin
endef

$(eval $(call BuildPackage,tplink-deco-x50-poe-v2-uboot))

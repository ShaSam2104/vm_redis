#!/bin/bash

# add 2 gigs of storage to the ext4 rootfs
qemu-img resize ubuntu.ext4 +2G

# attach loop device to ext4
sudo losetup -fP ubuntu.ext4

# resize the vm partition so that the rootfs knows how much space is available
#
#    in order to find which loop device your ext4 file is attached to, run:
#    losetup -a
#    then use that loop device, say loop0 (replace 0 with yours), in the following commands

sudo e2fsck -f /dev/loop0

sudo resize2fs /dev/loop0

sudo losetup -d /dev/loop0


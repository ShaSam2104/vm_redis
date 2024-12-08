#!/bin/bash

# Function to boot a Firecracker microVM on demand with TUN/TAP networking
boot_vm() {
    local VM_ID=$1  # Unique ID for this VM
    local TAP_DEV="tap${VM_ID}"
    local MAC_ADDR="06:00:AC:10:00:${VM_ID}"
    local VM_IP="172.16.0.${VM_ID}"
    local HOST_IP="172.16.0.1"
    local CONFIG_FILE="vm${VM_ID}_config.json"
    local API_SOCKET="/tmp/firecracker_${VM_ID}.socket"

    sudo ip tuntap add "tap${VM_ID}" mode tap
    # sudo ip addr add "172.16.0.${VM_ID}/24" dev "tap${VM_ID}"
    sudo ip link set "tap${VM_ID}" up
    sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
    sudo iptables -t nat -A POSTROUTING -o eno1 -j MASQUERADE
    sudo iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    sudo iptables -A FORWARD -i "tap${VM_ID}" -o eno1 -j ACCEPT

    sudo ip link set dev "tap${VM_ID}" master br0

    # create a disk space for vm to write into
    # dd if=/dev/zero of="extra_storage_${VM_ID}.img" bs=2G count=1
    # mkfs.ext4 "extra_storage_${VM_ID}.img"

    # Create Firecracker config file
    cat > "$CONFIG_FILE" <<EOF
{
  "boot-source": {
    "kernel_image_path": "vmlinux-5.10.225",
    "boot_args": "console=ttyS0 reboot=k panic=1 pci=off",
    "initrd_path": null
  },
  "drives": [
    {
      "drive_id": "rootfs",
      "partuuid": null,
      "cache_type": "Unsafe",
      "path_on_host": "ubuntu-24.04.ext4",
      "is_root_device": true,
      "io_engine": "Sync",
      "is_read_only": false,
      "rate_limiter": null,
      "socket": null
    },
    {
      "drive_id": "extra_storage",
      "path_on_host": "extra_storage_${VM_ID}.img",
      "is_root_device": false,
      "is_read_only": false
    }
  ],
  "network-interfaces": [
    {
      "iface_id": "eth0",
      "host_dev_name": "$TAP_DEV",
      "guest_mac": "$MAC_ADDR"
    }
  ],
  "machine-config": {
    "vcpu_count": 2,
    "mem_size_mib": 2048,
    "smt": false,
    "track_dirty_pages": false,
    "huge_pages": "None"
  }
}
EOF

    # Remove API unix socket
    sudo rm -f "$API_SOCKET"

    # Start Firecracker with the configuration file
    sudo ./firecracker --api-sock "$API_SOCKET" --config-file "$CONFIG_FILE"

    # Configure networking inside the VM
    # You'll need to use SSH or another mechanism to set the following in the VM:
    # ip addr add "$VM_IP"/24 dev eth0
    # ip link set eth0 up
    # ip route add default via "$HOST_IP"
    # echo "nameserver 8.8.8.8" > /etc/resolv.conf
}


boot_vm $1

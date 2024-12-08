#!/bin/bash

sudo ip link add name br0 type bridge
sudo ip address add 10.20.24.2/24 dev br0
sudo iptables -t nat -A POSTROUTING -o br0 -j MASQUERADE
sudo ip link set br0 up

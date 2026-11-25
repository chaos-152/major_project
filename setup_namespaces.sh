#!/bin/bash

set -e

if [ "$EUID" -ne 0 ]; then
    echo "[!] Please run with sudo: sudo ./setup_namespaces.sh"
    exit 1
fi

echo "[*] Initializing 5G UE Network Namespaces..."

for n in 1 2; do
    ip netns del ue$n 2>/dev/null || true
    ip link del veth-g$n 2>/dev/null || true
done

for n in 1 2; do
    echo "  -> Configuring ue$n (veth-ue$n <---> veth-g$n)..."
    ip netns add ue$n
    ip link add veth-ue$n type veth peer name veth-g$n
    ip link set veth-ue$n netns ue$n
    ip addr add 10.200.$n.1/24 dev veth-g$n
    ip link set veth-g$n up
    ip netns exec ue$n ip addr add 10.200.$n.2/24 dev veth-ue$n
    ip netns exec ue$n ip link set veth-ue$n up
    ip netns exec ue$n ip link set lo up
done

sysctl -w net.ipv4.ip_forward=1 >/dev/null

echo "[*] Network namespaces ue1 and ue2 ready."
echo "    gNB link interfaces: veth-g1 (10.200.1.1), veth-g2 (10.200.2.1)"
echo "    UE link interfaces:  ue1:veth-ue1 (10.200.1.2), ue2:veth-ue2 (10.200.2.2)"

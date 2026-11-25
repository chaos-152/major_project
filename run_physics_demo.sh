#!/usr/bin/env bash
# Interactive launcher for the Physics-to-Bits 3-Program Suite over Open5GS + UERANSIM
# Usage:
#   sudo ./run_physics_demo.sh              # Live interactive over Open5GS ue1/ue2
#   ./run_physics_demo.sh --loopback        # Live interactive on localhost (no sudo)
#   ./run_physics_demo.sh --loopback-test   # Automated smoke test on localhost

set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [[ "${1:-}" == "--loopback-test" ]]; then
    echo "[*] Running interactive smoke test on loopback..."
    python3 prog3_rs_resilience.py --loopback --timeout 10 > /tmp/5g_p3.log 2>&1 &
    P3_PID=$!
    python3 prog2_crc_detector.py --loopback --timeout 10 > /tmp/5g_p2.log 2>&1 &
    P2_PID=$!
    sleep 0.3
    printf "clear\nHELLO 5G SURATHKAL\nedge\nHELLO PROFESSOR\nedge\nNITK 5G TEST\ncenter\nHELLO FROM SUB6\nquit\n" \
        | python3 prog1_tx_channel.py --loopback --seed 42
    wait $P2_PID $P3_PID
    echo ""
    cat /tmp/5g_p2.log
    echo ""
    cat /tmp/5g_p3.log
    exit 0
fi

if [[ "${1:-}" == "--loopback" ]]; then
    echo "[*] Launching P2 & P3 in background (logs: /tmp/5g_p2.log, /tmp/5g_p3.log)..."
    python3 prog3_rs_resilience.py --loopback > /tmp/5g_p3.log 2>&1 &
    P3_PID=$!
    python3 prog2_crc_detector.py --loopback > /tmp/5g_p2.log 2>&1 &
    P2_PID=$!
    sleep 0.3
    python3 prog1_tx_channel.py --loopback --seed 42
    wait $P2_PID $P3_PID
    echo ""
    cat /tmp/5g_p2.log
    echo ""
    cat /tmp/5g_p3.log
    exit 0
fi

if [ "$EUID" -ne 0 ]; then
    echo "[!] Run with sudo for Open5GS/UERANSIM namespaces: sudo ./run_physics_demo.sh"
    echo "    Or offline without sudo: ./run_physics_demo.sh --loopback"
    exit 1
fi

IP1=$(ip netns exec ue1 ip -4 addr show dev uesimtun0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1 || true)
IP2=$(ip netns exec ue2 ip -4 addr show dev uesimtun0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1 || true)
if [ -z "$IP1" ] || [ -z "$IP2" ]; then
    echo "[!] uesimtun0 not ready in ue1/ue2. Starting 5G stack first..."
    bash "$DIR/start_5g_stack.sh"
fi

echo "[*] Launching P3 & P2 in netns ue2 (logs: /tmp/5g_p2.log, /tmp/5g_p3.log)..."
python3 prog3_rs_resilience.py > /tmp/5g_p3.log 2>&1 &
P3_PID=$!
python3 prog2_crc_detector.py > /tmp/5g_p2.log 2>&1 &
P2_PID=$!
sleep 0.4

python3 prog1_tx_channel.py --scenario urban_high --seed 42
wait $P2_PID $P3_PID

echo ""
cat /tmp/5g_p2.log
echo ""
cat /tmp/5g_p3.log

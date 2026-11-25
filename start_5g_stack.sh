#!/usr/bin/env bash

set -e
ROOT_DIR="/home/realfifth/UERANSIM"
BUILD_DIR="$ROOT_DIR/build"
CONFIG_DIR="$ROOT_DIR/config"
LOG_DIR="/tmp/5g_logs"

mkdir -p "$LOG_DIR"

if [ "$EUID" -ne 0 ]; then
    echo "[!] Please run with sudo: sudo ./start_5g_stack.sh"
    exit 1
fi

echo "[1/5] Terminating any dangling UERANSIM processes..."
killall -9 nr-gnb nr-ue > /dev/null 2>&1 || true
sleep 1

echo "[2/5] Initializing network namespaces ue1 and ue2..."
bash "$ROOT_DIR/emulation/setup_namespaces.sh"

echo "[3/5] Verifying Open5GS Core status..."
systemctl is-active open5gs-amfd > /dev/null 2>&1 || systemctl start open5gs-amfd
systemctl is-active open5gs-upfd > /dev/null 2>&1 || systemctl start open5gs-upfd

echo "[4/5] Launching Base Station (gNB linkIp: 0.0.0.0)..."
"$BUILD_DIR/nr-gnb" -c "$CONFIG_DIR/open5gs-gnb.yaml" > "$LOG_DIR/gnb1.log" 2>&1 &
GNB1_PID=$!
sleep 1

echo "[5/5] Launching UEs inside isolated network namespaces..."
echo "  -> Starting UE 1 in netns ue1..."
ip netns exec ue1 "$BUILD_DIR/nr-ue" -c "$CONFIG_DIR/open5gs-ue.yaml" > "$LOG_DIR/ue1.log" 2>&1 &
UE1_PID=$!

echo "  -> Starting UE 2 in netns ue2..."
ip netns exec ue2 "$BUILD_DIR/nr-ue" -c "$CONFIG_DIR/open5gs-ue2.yaml" > "$LOG_DIR/ue2.log" 2>&1 &
UE2_PID=$!

echo ""
echo "======================================================================"
echo "  5G STACK STATUS (NAMESPACES ACTIVE)"
echo "======================================================================"
echo "  gNB PID: $GNB1_PID | Logs: $LOG_DIR/gnb1.log"
echo "  UE 1 PID: $UE1_PID  | Logs: $LOG_DIR/ue1.log (netns ue1)"
echo "  UE 2 PID: $UE2_PID  | Logs: $LOG_DIR/ue2.log (netns ue2)"
echo ""

echo "[+] Waiting for PDU session & IPv4 address allocation on uesimtun0..."
TIMEOUT_SECS=20
POLL_INTERVAL=0.5
MAX_ATTEMPTS=$(awk -v t="$TIMEOUT_SECS" -v p="$POLL_INTERVAL" 'BEGIN {print int(t/p)}')
ATTEMPTS=0
IP1=""
IP2=""

while [ "$ATTEMPTS" -lt "$MAX_ATTEMPTS" ]; do
    if [ -z "$IP1" ]; then
        IP1=$(ip netns exec ue1 ip -4 addr show dev uesimtun0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1)
    fi
    if [ -z "$IP2" ]; then
        IP2=$(ip netns exec ue2 ip -4 addr show dev uesimtun0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1)
    fi

    if [ -n "$IP1" ] && [ -n "$IP2" ]; then
        break
    fi

    sleep "$POLL_INTERVAL"
    ATTEMPTS=$((ATTEMPTS + 1))
done

if [ -n "$IP1" ] && [ -n "$IP2" ]; then
    echo "[✓] 5G Stack Ready! UE1: $IP1 | UE2: $IP2 (PDU sessions established)"
else
    echo "[!] Warning: PDU session setup incomplete after ${TIMEOUT_SECS}s."
    echo "    Check logs: $LOG_DIR/ue1.log and $LOG_DIR/ue2.log"
fi

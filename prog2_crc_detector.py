#!/usr/bin/env python3
"""
Program 2: UE 2 Pure Mathematical CRC-16 Detector & Observability Tap (Open5GS + UERANSIM)

Listens on UE 2's uesimtun0 interface (10.45.0.x) for incoming 28 GHz mmWave (:5001)
and 3.5 GHz Sub-6 retransmission (:5002) packets, runs pure polynomial long division:
    (M(x) * x^16 + CRC(x)) mod G(x) == 0x0000   [G(x) = 0x1021]
with ZERO cheat flags, logs live corruption, and forwards untouched raw codewords
to Program 3 (127.0.0.1:5003 inside netns ue2).

Pass --loopback to run offline on 127.0.0.1 without sudo/namespaces.
"""

from __future__ import annotations

import argparse
import select
import socket
import sys

from core import LINK_MMWAVE, crc16_verify, detect_ue_ips, enter_netns, unpack_frame

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def _printable_ascii(raw: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Program 2: UE 2 Mathematical CRC-16 Detector")
    parser.add_argument("--loopback", action="store_true", help="Run on 127.0.0.1 without Open5GS netns")
    parser.add_argument("--bind-ip", default="", help="Override bind IP")
    parser.add_argument("--mmwave-port", type=int, default=5001, help="Incoming 28 GHz mmWave UDP port")
    parser.add_argument("--sub6-port", type=int, default=5002, help="Incoming 3.5 GHz Sub-6 UDP port")
    parser.add_argument("--p3-ip", default="127.0.0.1", help="Program 3 forward IP (inside ue2 netns)")
    parser.add_argument("--p3-port", type=int, default=5003, help="Program 3 forward UDP port")
    parser.add_argument("--timeout", type=float, default=0.0, help="Idle timeout in seconds (0 = wait forever)")
    args = parser.parse_args()

    if args.loopback:
        bind_ip = args.bind_ip or "127.0.0.1"
        ns_label = f"Loopback ({bind_ip})"
    else:
        _, ip2 = detect_ue_ips()
        bind_ip = args.bind_ip or ip2
        if not bind_ip:
            print("[!] Error: uesimtun0 not found in netns ue2.")
            print("    Run: sudo ./start_5g_stack.sh  (or pass --loopback)")
            sys.exit(1)
        enter_netns("ue2")
        ns_label = f"netns ue2 / uesimtun0 ({bind_ip})"

    sock_mmw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_mmw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_mmw.bind((bind_ip, args.mmwave_port))

    sock_sub6 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_sub6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_sub6.bind((bind_ip, args.sub6_port))

    fwd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print("=" * 88, flush=True)
    print("PROGRAM 2: UE 2 PURE MATHEMATICAL CRC-16 DETECTOR (NO CHEAT FLAGS)", flush=True)
    print("=" * 88, flush=True)
    print(f"Interface  : {ns_label} (mmW:{args.mmwave_port}, Sub6:{args.sub6_port})", flush=True)
    print(f"Forwarding : Raw wire stream -> Program 3 at {args.p3_ip}:{args.p3_port}", flush=True)
    print("Check      : (M(x) * x^16 + CRC(x)) mod G(x) == 0x0000  [G(x)=0x1021]", flush=True)
    print("Note       : Header x/Es_N0 are display-only telemetry (never used in decisions);", flush=True)
    print("             P2 never sees the original text, so it detects corruption without diffing.", flush=True)
    print("=" * 88, flush=True)

    eos_seen = {args.mmwave_port: False, args.sub6_port: False}
    mmw_total = 0
    mmw_corrupted = 0
    sub6_total = 0
    sub6_corrupted = 0

    try:
        while not all(eos_seen.values()):
            timeout_arg = args.timeout if args.timeout > 0 else None
            readable, _, _ = select.select([sock_mmw, sock_sub6], [], [], timeout_arg)
            if not readable:
                print(f"{YELLOW}[P2] Idle timeout reached; exiting.{RESET}", flush=True)
                break

            for s in readable:
                raw_pkt, _ = s.recvfrom(4096)
                try:
                    frame = unpack_frame(raw_pkt)
                except ValueError as e:
                    print(f"{RED}[P2 REJECTED MALFORMED PACKET] {e}{RESET}", flush=True)
                    continue
                fwd_sock.sendto(raw_pkt, (args.p3_ip, args.p3_port))

                port = s.getsockname()[1]
                if frame["eos"]:
                    eos_seen[port] = True
                    continue

                cw = frame["codeword"]
                nsym = frame["rs_nsym"]
                msg_with_crc = cw[:-nsym]
                payload = msg_with_crc[:-2]
                passed, rem = crc16_verify(msg_with_crc)

                status = f"{GREEN}[✓ PASS]     {RESET}" if passed else f"{RED}[✗ CORRUPTED]{RESET}"
                if frame["link_id"] == LINK_MMWAVE:
                    mmw_total += 1
                    if not passed:
                        mmw_corrupted += 1
                    link_tag = f"{CYAN}[28 GHz]     {RESET}"
                else:
                    sub6_total += 1
                    if not passed:
                        sub6_corrupted += 1
                    link_tag = f"{YELLOW}[3.5 GHz RETX]{RESET}"

                print(
                    f"seq={frame['seq']:04d} {link_tag} x={frame['x_m']:+5.2f}m "
                    f"Es/N0={frame['snr_db']:+6.2f}dB | "
                    f"R(x)=0x{rem:04X} {status} | \"{_printable_ascii(payload)}\"",
                    flush=True,
                )
    except KeyboardInterrupt:
        pass
    finally:
        sock_mmw.close()
        sock_sub6.close()
        fwd_sock.close()

    print("=" * 88, flush=True)
    print(
        f"[P2 Summary] 28 GHz: {mmw_total} rx ({mmw_corrupted} CRC-corrupted) | "
        f"3.5 GHz Sub-6 RETX: {sub6_total} rx ({sub6_corrupted} CRC-corrupted)",
        flush=True,
    )
    print("=" * 88, flush=True)


if __name__ == "__main__":
    main()

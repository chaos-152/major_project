#!/usr/bin/env python3
"""
Program 1: Interactive UE 1 Transmitter & App-Layer 5G Channel Emulator (Open5GS + UERANSIM)

Type any message to send over the Open5GS UPF tunnel:
  1. Splits long messages into fixed 18-byte chunks (--chunk-size 18) so every chunk
     fits a shortened RS(24, 20) codeword (t=2), keeping grazing-edge RS survival high.
  2. Applies 3GPP TR 38.901 Model B (4-edge) diffraction at 28 GHz + Gray 16-QAM + AWGN.
  3. Sends ONLY on 28 GHz mmWave (:5001) first and waits for ACK/NACK from Program 3 (:5004).
  4. If Program 3 drops the mmWave packet and returns NACK, Program 1 retransmits that
     chunk over 3.5 GHz Sub-6 (:5002) using the same diffraction model.
  5. Measures real end-to-end RTT per chunk via time.perf_counter() from first send to ACK
     (a Sub-6 rescue naturally shows the real extra round trip through Open5GS).

Position commands at the prompt:
  clear    -> x = -0.75 m (unobstructed LoS)
  edge     -> x = -0.22 m (grazing edge: small damage, RS repairs on mmWave)
  center   -> x =  0.00 m (dead-center blockage: mmWave drops -> Sub-6 retransmit)
  x=<val>  -> custom pedestrian offset in meters (e.g. x=-0.18)
  quit     -> send EOS to P2/P3 and exit

Pass --loopback to run offline on 127.0.0.1 without sudo/namespaces.
"""

from __future__ import annotations

import argparse
import socket
import sys
import time

import numpy as np

from core import (
    FB_ACK_MMW,
    FB_ACK_SUB6,
    FB_NACK_MMW,
    LINK_MMWAVE,
    LINK_SUB6,
    SCENARIOS,
    crc16_append,
    detect_ue_ips,
    enter_netns,
    pack_frame,
    rs_encode,
    tr38901_4edge_loss_db,
    transmit_bytes_over_channel,
    unpack_feedback,
)

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

PRESETS = {
    "clear": -0.75,
    "edge": -0.22,
    "center": 0.00,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Program 1: Interactive UE 1 TX & 5G Channel Emulator")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), default="urban_high")
    parser.add_argument("--rs-nsym", type=int, default=4, help="RS parity bytes (2t); default 4 -> t=2")
    parser.add_argument("--chunk-size", type=int, default=18, help="Max payload bytes per RS block (default 18 -> RS(24,20))")
    parser.add_argument("--max-sub6-retries", type=int, default=2, help="Max Sub-6 retransmission attempts after mmWave NACK (default 2)")
    parser.add_argument("--loopback", action="store_true", help="Run on 127.0.0.1 without Open5GS netns")
    parser.add_argument("--dest-ip", default="", help="Override UE 2 destination IP")
    parser.add_argument("--bind-ip", default="", help="Override UE 1 source IP")
    parser.add_argument("--mmwave-port", type=int, default=5001, help="28 GHz mmWave UDP port")
    parser.add_argument("--sub6-port", type=int, default=5002, help="3.5 GHz Sub-6 UDP port")
    parser.add_argument("--fb-port", type=int, default=5004, help="ACK/NACK feedback UDP port from P3")
    parser.add_argument("--d1", type=float, default=1.5, help="TX to pedestrian plane distance (m)")
    parser.add_argument("--d2", type=float, default=10.0, help="Pedestrian plane to RX distance (m)")
    parser.add_argument("--width", type=float, default=None, help="Override obstacle width W (m)")
    parser.add_argument("--height", type=float, default=1.7, help="Obstacle height H (m)")
    parser.add_argument("--z-ray", type=float, default=1.2, help="LoS ray height at blocker plane (m)")
    parser.add_argument("--snr-los", type=float, default=22.0, help="Unobstructed LoS Es/N0 (dB)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    args = parser.parse_args()

    if args.rs_nsym < 2 or args.rs_nsym % 2 != 0:
        print(f"[!] Invalid --rs-nsym {args.rs_nsym} (must be even and >= 2).")
        sys.exit(1)
    if args.chunk_size < 1 or args.chunk_size + 2 + args.rs_nsym > 255:
        print(f"[!] Invalid --chunk-size {args.chunk_size} for GF(2^8) RS with nsym={args.rs_nsym}.")
        sys.exit(1)
    if args.max_sub6_retries < 0:
        print(f"[!] Invalid --max-sub6-retries {args.max_sub6_retries} (must be >= 0).")
        sys.exit(1)
    if args.d1 <= 0 or args.d2 <= 0 or args.height <= 0:
        print(f"[!] Invalid geometry: d1={args.d1}, d2={args.d2}, height={args.height} must be > 0.")
        sys.exit(1)
    if args.width is not None and args.width <= 0:
        print(f"[!] Invalid --width {args.width} (must be > 0).")
        sys.exit(1)
    if not (-300.0 <= args.snr_los <= 300.0):
        print(f"[!] Invalid --snr-los {args.snr_los} (must be in [-300, 300] dB).")
        sys.exit(1)

    sc_key = args.scenario
    sc = SCENARIOS[sc_key]
    width = args.width if args.width is not None else float(sc["obstacle_width_w"])
    bw_mhz = int(sc["bandwidth_mhz"])

    def presets_for_width(w: float) -> dict[str, float]:
        return {
            "clear": -(w / 2.0 + 0.50),
            "edge": -(w / 2.0 - 0.03),
            "center": 0.00,
        }

    if args.loopback:
        src_ip = args.bind_ip or "127.0.0.1"
        dst_ip = args.dest_ip or "127.0.0.1"
        transport_label = f"Loopback {src_ip} -> {dst_ip}"
    else:
        ip1, ip2 = detect_ue_ips()
        src_ip = args.bind_ip or ip1
        dst_ip = args.dest_ip or ip2
        if not src_ip or not dst_ip:
            print("[!] Error: uesimtun0 not found in netns ue1/ue2.")
            print("    Run: sudo ./start_5g_stack.sh  (or pass --loopback)")
            sys.exit(1)
        enter_netns("ue1")
        transport_label = f"Open5GS UPF Tunnel ue1({src_ip}) -> ue2({dst_ip})"

    tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx_sock.bind((src_ip, 0))

    fb_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fb_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    fb_sock.bind((src_ip, args.fb_port))
    fb_sock.settimeout(3.0)

    rng = np.random.default_rng(args.seed)
    x_pos = presets_for_width(width)["clear"]
    seq = 0
    mmw_rtts_ms: list[float] = []
    sub6_rtts_ms: list[float] = []

    def show_link_state(x: float) -> tuple[float, float, float, float]:
        l_mmw = tr38901_4edge_loss_db(x, args.d1, args.d2, 28e9, W=width, H=args.height, z_ray=args.z_ray)
        l_sub6 = tr38901_4edge_loss_db(x, args.d1, args.d2, 3.5e9, W=width, H=args.height, z_ray=args.z_ray)
        return l_mmw, args.snr_los - l_mmw, l_sub6, args.snr_los - l_sub6

    print("=" * 92)
    print("PROGRAM 1: INTERACTIVE UE 1 TX & APP-LAYER 5G CHANNEL EMULATOR (STOP-AND-WAIT ARQ)")
    print("=" * 92)
    print(f"Transport : {transport_label} (mmW:{args.mmwave_port}, Sub6:{args.sub6_port}, FB:{args.fb_port})")
    print(f"Scenario  : {sc_key} — {sc['name']} (W={width} m, H={args.height} m, BW={bw_mhz} MHz, d1={args.d1} m, d2={args.d2} m)")
    print(
        f"Coding    : Chunked {args.chunk_size}B/block + CRC-16 + Systematic RS(N, K) over GF(2^8), "
        f"t={args.rs_nsym // 2}"
    )
    print(f"Channel   : 3GPP TR 38.901 Model B (4-edge) | Fixed Gray 16-QAM | LoS Es/N0={args.snr_los:.1f} dB")
    print("Timing    : Real end-to-end RTT measured via time.perf_counter() (first send -> final ACK)")
    print("-" * 92)
    print("Position  : 'clear' | 'edge' | 'center' | 'x=<m>'   (auto-scales to blocker width W)")
    print("Scenarios : 'scenarios' to list, or type name directly (urban_high, urban_mild, urban_low, rural_high, rural_mild, rural_low)")
    print("Send/Exit : Type ANY message to transmit | 'quit' to exit")
    print("=" * 92)

    try:
        while True:
            l_mmw, snr_mmw, l_sub6, snr_sub6 = show_link_state(x_pos)
            prompt = (
                f"\n[{sc_key} W={width}m | x={x_pos:+.2f}m | 28GHz:{snr_mmw:+5.1f}dB | 3.5GHz:{snr_sub6:+5.1f}dB] "
                f"msg/cmd > "
            )
            try:
                line = input(prompt).strip()
            except EOFError:
                break

            if not line:
                continue

            low = line.lower()
            if low in ("quit", "exit"):
                break
            if low == "scenarios":
                print(f"{CYAN}Available scenarios (from scenario_params.py):{RESET}")
                for k, v in SCENARIOS.items():
                    mark = " *" if k == sc_key else ""
                    print(
                        f"  {k:12s} | W={v['obstacle_width_w']:4.1f}m | v={v['mean_blocker_velocity_v']:4.1f}m/s | "
                        f"BW={v['bandwidth_mhz']:3d} MHz | {v['name']}{mark}"
                    )
                continue
            if low.startswith("scenario ") or low in SCENARIOS:
                target = low.split(None, 1)[1].strip() if low.startswith("scenario ") else low
                if target not in SCENARIOS:
                    print(f"{RED}[!] Unknown scenario {target!r}. Type 'scenarios' to list.{RESET}")
                    continue
                sc_key = target
                sc = SCENARIOS[sc_key]
                width = float(sc["obstacle_width_w"])
                bw_mhz = int(sc["bandwidth_mhz"])
                x_pos = presets_for_width(width)["clear"]
                l_mmw, snr_mmw, l_sub6, snr_sub6 = show_link_state(x_pos)
                print(
                    f"{CYAN}[SCENARIO] Switched to {sc_key} ({sc['name']}): "
                    f"W={width}m, BW={bw_mhz} MHz | reset to clear x={x_pos:+.2f}m "
                    f"(edge={presets_for_width(width)['edge']:+.2f}m, center=0.00m){RESET}"
                )
                continue
            cur_presets = presets_for_width(width)
            if low in cur_presets:
                x_pos = cur_presets[low]
                l_mmw, snr_mmw, l_sub6, snr_sub6 = show_link_state(x_pos)
                print(
                    f"{CYAN}[POS] x={x_pos:+.2f}m ({low}, W={width}m) -> "
                    f"28GHz L={l_mmw:.2f}dB (Es/N0={snr_mmw:+.2f}dB) | "
                    f"3.5GHz L={l_sub6:.2f}dB (Es/N0={snr_sub6:+.2f}dB){RESET}"
                )
                continue
            if low.startswith("x="):
                try:
                    new_x = float(low.split("=", 1)[1])
                    if abs(new_x) > 30.0:
                        print(f"{RED}[!] x={new_x} out of supported range [-30.0, +30.0] m.{RESET}")
                        continue
                    x_pos = new_x
                    l_mmw, snr_mmw, l_sub6, snr_sub6 = show_link_state(x_pos)
                    print(
                        f"{CYAN}[POS] x={x_pos:+.2f}m -> "
                        f"28GHz L={l_mmw:.2f}dB (Es/N0={snr_mmw:+.2f}dB) | "
                        f"3.5GHz L={l_sub6:.2f}dB (Es/N0={snr_sub6:+.2f}dB){RESET}"
                    )
                except ValueError:
                    print(f"{RED}[!] Invalid x value. Example: x=-0.20{RESET}")
                continue

            raw_bytes = line.encode("utf-8")
            chunks = [raw_bytes[i : i + args.chunk_size] for i in range(0, len(raw_bytes), args.chunk_size)]
            if len(chunks) > 1:
                print(f"  {CYAN}[CHUNK] Split {len(raw_bytes)}B message into {len(chunks)} blocks of <={args.chunk_size}B (keeps RS t=2 effective){RESET}")

            for c_idx, payload in enumerate(chunks, start=1):
                msg_with_crc = crc16_append(payload)
                clean_cw = rs_encode(msg_with_crc, nsym=args.rs_nsym)
                chunk_tag = f" ({c_idx}/{len(chunks)})" if len(chunks) > 1 else ""

                # Precompute channel-corrupted bytes BEFORE starting the network RTT timer
                # (so perf_counter measures socket + Open5GS UPF + P2/P3 decode, not numpy)
                rx_mmw = transmit_bytes_over_channel(clean_cw, snr_mmw, rng)
                rx_sub6_pool = [
                    transmit_bytes_over_channel(clean_cw, snr_sub6, rng)
                    for _ in range(args.max_sub6_retries)
                ]
                pkt_mmw = pack_frame(seq, bw_mhz, x_pos, snr_mmw, LINK_MMWAVE, args.rs_nsym, rx_mmw)

                t0 = time.perf_counter()
                fb_code = None
                for mmw_try in range(2):  # retry once if ACK/NACK packet is lost (P3 suppresses duplicates)
                    tx_sock.sendto(pkt_mmw, (dst_ip, args.mmwave_port))
                    if mmw_try == 0:
                        print(
                            f"  -> [TX 28 GHz] seq={seq:04d}{chunk_tag} | RS({len(clean_cw)},{len(msg_with_crc)}) | "
                            f"L={l_mmw:.2f} dB, Es/N0={snr_mmw:+.2f} dB"
                        )
                    else:
                        print(f"  {YELLOW}[RETRY 28 GHz] ACK timeout -> resending seq={seq:04d} (P3 deduplicates){RESET}")
                    try:
                        while True:
                            fb_raw, _ = fb_sock.recvfrom(256)
                            fb_seq, code = unpack_feedback(fb_raw)
                            if fb_seq == seq:
                                fb_code = code
                                break
                        break
                    except socket.timeout:
                        continue

                if fb_code is None:
                    print(f"  {RED}[TIMEOUT] No ACK/NACK from Program 3 after retry (is P2/P3 running?){RESET}")
                    seq += 1
                    continue

                if fb_code == FB_ACK_MMW:
                    rtt_ms = (time.perf_counter() - t0) * 1000.0
                    mmw_rtts_ms.append(rtt_ms)
                    print(f"  {GREEN}[ACK 28 GHz] Delivered on mmWave! | Measured RTT = {rtt_ms:.2f} ms (1 hop){RESET}")
                elif fb_code == FB_NACK_MMW:
                    rescued = False
                    for attempt_idx, rx_sub6 in enumerate(rx_sub6_pool, start=1):
                        pkt_sub6 = pack_frame(seq, bw_mhz, x_pos, snr_sub6, LINK_SUB6, args.rs_nsym, rx_sub6)
                        tx_sock.sendto(pkt_sub6, (dst_ip, args.sub6_port))
                        print(
                            f"  {YELLOW}[NACK 28 GHz -> SUB-6 ATTEMPT {attempt_idx}/{len(rx_sub6_pool)}] "
                            f"Retransmitting on 3.5 GHz (L={l_sub6:.2f} dB, Es/N0={snr_sub6:+.2f} dB)...{RESET}"
                        )
                        try:
                            code2 = None
                            while True:
                                fb_raw, _ = fb_sock.recvfrom(256)
                                fb_seq, c = unpack_feedback(fb_raw)
                                if fb_seq == seq:
                                    code2 = c
                                    break
                            rtt_ms = (time.perf_counter() - t0) * 1000.0
                            if code2 == FB_ACK_SUB6:
                                sub6_rtts_ms.append(rtt_ms)
                                print(
                                    f"  {GREEN}[ACK 3.5 GHz] Rescued via Sub-6 (attempt {attempt_idx})! | "
                                    f"Measured RTT = {rtt_ms:.2f} ms (2+ hops){RESET}"
                                )
                                rescued = True
                                break
                            else:
                                print(
                                    f"  {RED}[NACK 3.5 GHz] Sub-6 attempt {attempt_idx}/{len(rx_sub6_pool)} failed ({rtt_ms:.2f} ms).{RESET}"
                                )
                        except socket.timeout:
                            print(f"  {RED}[TIMEOUT] No Sub-6 ACK on attempt {attempt_idx}/{len(rx_sub6_pool)}.{RESET}")
                    if not rescued:
                        print(f"  {RED}[FAILED] Exhausted {len(rx_sub6_pool)} Sub-6 retries for seq={seq:04d}.{RESET}")

                seq += 1
    except KeyboardInterrupt:
        pass
    finally:
        eos_mmw = pack_frame(seq, 0, 0.0, 0.0, LINK_MMWAVE, args.rs_nsym, b"", eos=True)
        eos_sub6 = pack_frame(seq, 0, 0.0, 0.0, LINK_SUB6, args.rs_nsym, b"", eos=True)
        tx_sock.sendto(eos_mmw, (dst_ip, args.mmwave_port))
        tx_sock.sendto(eos_sub6, (dst_ip, args.sub6_port))
        tx_sock.close()
        fb_sock.close()
        print(f"\n[UE 1] Session ended ({seq} blocks sent).")
        if mmw_rtts_ms:
            samples = mmw_rtts_ms[1:] if len(mmw_rtts_ms) > 1 else mmw_rtts_ms
            note = " (warm-up #1 excluded)" if len(mmw_rtts_ms) > 1 else ""
            print(f"  Median Measured RTT (28 GHz delivered, 1 hop) : {np.median(samples):.2f} ms (n={len(samples)}{note})")
        if sub6_rtts_ms:
            print(f"  Median Measured RTT (Sub-6 rescued, 2 hops)   : {np.median(sub6_rtts_ms):.2f} ms (n={len(sub6_rtts_ms)})")


if __name__ == "__main__":
    main()

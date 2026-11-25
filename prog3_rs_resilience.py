#!/usr/bin/env python3
"""
Program 3: UE 2 GF(2^8) RS Syndrome Decoder & Reactive Sub-6 ARQ Controller (Open5GS + UERANSIM)

Receives raw wire codewords forwarded by Program 2 (127.0.0.1:5003 inside netns ue2):
  - Header fields x_m and snr_db are display-only telemetry (never used by RS/CRC logic).
  - On 28 GHz mmWave packet:
      1. Runs GF(2^8) syndromes S_j = r(alpha^j) + Berlekamp-Massey + Chien + Forney.
      2. Re-verifies CRC-16 post-decode (catches any RS miscorrection).
      3. If clean or repaired (<= t bytes): prints received -> repaired text + exact fixed
         byte positions, delivers payload, and sends ACK to UE 1 (:5004).
      4. If uncorrectable (> t bytes): DROPS mmWave packet & sends NACK to UE 1 (:5004)
         so UE 1 retransmits over the 3.5 GHz Sub-6 anchor.
  - On 3.5 GHz Sub-6 retransmission:
      Decodes, verifies CRC-16, delivers payload, and sends Sub-6 ACK to UE 1.

Pass --loopback to run offline on 127.0.0.1 without sudo/namespaces.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
import socket
import sys

from core import (
    FB_ACK_MMW,
    FB_ACK_SUB6,
    FB_NACK_MMW,
    FB_NACK_SUB6,
    LINK_MMWAVE,
    NR_BAND_PROFILES,
    crc16_verify,
    detect_ue_ips,
    enter_netns,
    nr_modelled_peak_rate_mbps,
    pack_feedback,
    rs_decode,
    thermal_noise_dbm,
    unpack_frame,
)

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


def _printable_ascii(raw: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in raw)


def _decode_and_verify(codeword: bytes, nsym: int):
    rs_res = rs_decode(codeword, nsym=nsym)
    if not rs_res.success:
        return False, False, rs_res, b""
    crc_ok, _ = crc16_verify(rs_res.message)
    if not crc_ok:
        return False, True, rs_res, rs_res.message[:-2]
    return True, False, rs_res, rs_res.message[:-2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Program 3: RS Syndrome Decoder & Sub-6 ARQ Controller")
    parser.add_argument("--loopback", action="store_true", help="Run on host loopback without Open5GS netns")
    parser.add_argument("--bind-ip", default="127.0.0.1", help="Bind IP for Program 2 forward stream")
    parser.add_argument("--port", type=int, default=5003, help="UDP port receiving forwarded frames from P2")
    parser.add_argument("--ue1-ip", default="", help="Override UE 1 IP for ACK/NACK feedback")
    parser.add_argument("--fb-port", type=int, default=5004, help="UE 1 ACK/NACK feedback UDP port")
    parser.add_argument("--timeout", type=float, default=0.0, help="Idle timeout in seconds (0 = wait forever)")
    args = parser.parse_args()

    if args.loopback:
        ue1_ip = args.ue1_ip or "127.0.0.1"
        ns_label = f"Host Loopback ({args.bind_ip}:{args.port} -> FB {ue1_ip}:{args.fb_port})"
    else:
        ip1, _ = detect_ue_ips()
        ue1_ip = args.ue1_ip or ip1
        if not ue1_ip:
            print("[!] Error: uesimtun0 not found in netns ue1/ue2.")
            print("    Run: sudo ./start_5g_stack.sh  (or pass --loopback)")
            sys.exit(1)
        enter_netns("ue2")
        ns_label = f"netns ue2 ({args.bind_ip}:{args.port} -> FB ue1:{ue1_ip}:{args.fb_port})"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.bind_ip, args.port))
    if args.timeout > 0:
        sock.settimeout(args.timeout)

    fb_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    r_peak_mmw = nr_modelled_peak_rate_mbps("mmwave")
    r_peak_sub6 = nr_modelled_peak_rate_mbps("sub6")
    nf_diff = (
        thermal_noise_dbm(NR_BAND_PROFILES["mmwave"]["bandwidth_hz"])
        - thermal_noise_dbm(NR_BAND_PROFILES["sub6"]["bandwidth_hz"])
    )

    print("=" * 102, flush=True)
    print("PROGRAM 3: GF(2^8) RS SYNDROME DECODER (BM + FORNEY) & REACTIVE SUB-6 RETRANSMISSION", flush=True)
    print("=" * 102, flush=True)
    print(f"Listening  : {ns_label}", flush=True)
    print(
        f"Modelled Link Peak (TS 38.306 structure, 1 layer, 16-QAM, Rc=0.75): "
        f"28GHz={r_peak_mmw:.1f} Mbps | 3.5GHz={r_peak_sub6:.1f} Mbps",
        flush=True,
    )
    print(
        f"Notes      : Noise floor delta +{nf_diff:.1f} dB (equal LoS Es/N0 assumes BF gain); "
        f"real RTT measured in P1 (perf_counter); x/Es_N0 are display-only.",
        flush=True,
    )
    print("=" * 102, flush=True)

    stats = {
        "blocks": 0,
        "mmw_clean": 0,
        "mmw_parity_only_fix": 0,
        "mmw_grazing_rs_fix": 0,
        "mmw_dropped_nack": 0,
        "rs_miscorrections_caught": 0,
        "sub6_rescued": 0,
        "sub6_failed": 0,
        "duplicates_suppressed": 0,
    }
    MAX_REPLAY_WINDOW = 4096
    delivered_seqs: OrderedDict[int, int] = OrderedDict()  # bounded seq -> ACK code
    seen_mmw_seqs: OrderedDict[int, None] = OrderedDict()

    def _record_bounded(cache: OrderedDict, key: int, val) -> None:
        cache[key] = val
        cache.move_to_end(key)
        while len(cache) > MAX_REPLAY_WINDOW:
            cache.popitem(last=False)

    eos_count = 0

    try:
        while eos_count < 2:
            try:
                raw_pkt, _ = sock.recvfrom(4096)
            except socket.timeout:
                print(f"{YELLOW}[P3] Idle timeout reached; exiting.{RESET}", flush=True)
                break

            try:
                frame = unpack_frame(raw_pkt)
            except ValueError as e:
                print(f"{RED}[P3 REJECTED MALFORMED PACKET] {e}{RESET}", flush=True)
                continue
            if frame["eos"]:
                eos_count += 1
                continue

            seq = frame["seq"]
            # Duplicate suppression: if this seq was already delivered (e.g. lost ACK),
            # re-send its ACK without delivering a duplicate to the application.
            if seq in delivered_seqs:
                stats["duplicates_suppressed"] += 1
                fb_sock.sendto(pack_feedback(seq, delivered_seqs[seq]), (ue1_ip, args.fb_port))
                print(
                    f"seq={seq:04d} | {CYAN}[DUP SUPPRESSED]  {RESET} | "
                    f"already delivered; re-sent ACK to UE 1",
                    flush=True,
                )
                continue

            nsym = frame["rs_nsym"]
            raw_payload = frame["codeword"][: -(nsym + 2)]
            ok, miscorr, rs_res, payload = _decode_and_verify(frame["codeword"], nsym)
            if miscorr:
                stats["rs_miscorrections_caught"] += 1

            if frame["link_id"] == LINK_MMWAVE:
                if seq not in seen_mmw_seqs:
                    _record_bounded(seen_mmw_seqs, seq, None)
                    stats["blocks"] += 1
                bw_hint = frame["step_idx"] if frame["step_idx"] in (50, 100, 200, 400) else 400
                cur_peak_mmw = nr_modelled_peak_rate_mbps("mmwave", bandwidth_mhz=bw_hint)
                if ok:
                    _record_bounded(delivered_seqs, seq, FB_ACK_MMW)
                    fb_sock.sendto(pack_feedback(seq, FB_ACK_MMW), (ue1_ip, args.fb_port))
                    if rs_res.errors_corrected == 0:
                        stats["mmw_clean"] += 1
                        print(
                            f"seq={seq:04d} x={frame['x_m']:+5.2f}m | {GREEN}[MMW CLEAN]       {RESET} | "
                            f"peak {cur_peak_mmw:5.1f} Mbps ({bw_hint}MHz) | S={rs_res.syndromes} | \"{_printable_ascii(payload)}\"",
                            flush=True,
                        )
                    elif rs_res.parity_only:
                        stats["mmw_parity_only_fix"] += 1
                        print(
                            f"seq={seq:04d} x={frame['x_m']:+5.2f}m | {CYAN}[MMW PARITY FIX]  {RESET} | "
                            f"peak {cur_peak_mmw:5.1f} Mbps ({bw_hint}MHz) | pos={rs_res.error_positions} | "
                            f"\"{_printable_ascii(payload)}\" (parity-only)",
                            flush=True,
                        )
                    else:
                        stats["mmw_grazing_rs_fix"] += 1
                        print(
                            f"seq={seq:04d} x={frame['x_m']:+5.2f}m | {CYAN}[MMW RS FIXED {rs_res.errors_corrected}B]{RESET} | "
                            f"peak {cur_peak_mmw:5.1f} Mbps ({bw_hint}MHz) | pos={rs_res.error_positions} | "
                            f"\"{_printable_ascii(raw_payload)}\" -> \"{_printable_ascii(payload)}\"",
                            flush=True,
                        )
                else:
                    stats["mmw_dropped_nack"] += 1
                    fb_sock.sendto(pack_feedback(seq, FB_NACK_MMW), (ue1_ip, args.fb_port))
                    reason = "post-RS CRC caught miscorrection" if miscorr else rs_res.reason
                    print(
                        f"seq={seq:04d} x={frame['x_m']:+5.2f}m | {RED}[MMW DROPPED->NACK]{RESET} | "
                        f"\"{_printable_ascii(raw_payload)}\" | {reason} -> requesting Sub-6",
                        flush=True,
                    )
            else:
                if ok:
                    stats["sub6_rescued"] += 1
                    _record_bounded(delivered_seqs, seq, FB_ACK_SUB6)
                    fb_sock.sendto(pack_feedback(seq, FB_ACK_SUB6), (ue1_ip, args.fb_port))
                    fix_note = (
                        f" (RS fixed pos={rs_res.error_positions}: \"{_printable_ascii(raw_payload)}\" -> \"{_printable_ascii(payload)}\")"
                        if rs_res.errors_corrected > 0
                        else f" \"{_printable_ascii(payload)}\""
                    )
                    print(
                        f"seq={seq:04d} x={frame['x_m']:+5.2f}m | {YELLOW}[SUB-6 RESCUED]   {RESET} | "
                        f"link peak {r_peak_sub6:5.1f} Mbps | 3.5GHz Es/N0={frame['snr_db']:+5.2f}dB |{fix_note}",
                        flush=True,
                    )
                else:
                    stats["sub6_failed"] += 1
                    fb_sock.sendto(pack_feedback(seq, FB_NACK_SUB6), (ue1_ip, args.fb_port))
                    print(
                        f"seq={seq:04d} x={frame['x_m']:+5.2f}m | {MAGENTA}[SUB-6 FAILED]    {RESET} | "
                        f"\"{_printable_ascii(raw_payload)}\" | {rs_res.reason}",
                        flush=True,
                    )
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        fb_sock.close()

    total = stats["blocks"]
    delivered = (
        stats["mmw_clean"]
        + stats["mmw_parity_only_fix"]
        + stats["mmw_grazing_rs_fix"]
        + stats["sub6_rescued"]
    )
    print("=" * 102, flush=True)
    print(f"[P3 Summary] Blocks received       : {total}", flush=True)
    print(f"  Delivered on 28 GHz (Clean)      : {stats['mmw_clean']}", flush=True)
    print(f"  Delivered on 28 GHz (Parity Fix) : {stats['mmw_parity_only_fix']}  (P2 showed PASS; P3 fixed parity)", flush=True)
    print(f"  Delivered on 28 GHz (RS Fixed)   : {stats['mmw_grazing_rs_fix']}", flush=True)
    print(f"  Dropped on 28 GHz (NACK -> Sub6) : {stats['mmw_dropped_nack']}", flush=True)
    print(f"  RS Miscorrections Caught by CRC  : {stats['rs_miscorrections_caught']}", flush=True)
    print(f"  Rescued on 3.5 GHz Sub-6 Retx    : {stats['sub6_rescued']}", flush=True)
    print(f"  Duplicate Deliveries Suppressed  : {stats['duplicates_suppressed']}", flush=True)
    print(f"  Sub-6 Retx Attempts Failed       : {stats['sub6_failed']}", flush=True)
    if total > 0:
        print(f"  End-to-End Delivery Rate         : {100.0 * delivered / total:.2f}% ({delivered}/{total})", flush=True)
    print("  (See Program 1 output for real measured end-to-end RTT via perf_counter.)", flush=True)
    print("=" * 102, flush=True)


if __name__ == "__main__":
    main()

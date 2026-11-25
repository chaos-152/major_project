"""
Core Physics-to-Bits 5G Module (consolidated):
  1. Scenarios          — 6 5G blockage scenarios (urban_high .. rural_low)
  2. Physics & Baseband — Exact Fresnel, 3GPP TR 38.901 Model B 4-edge diffraction,
                          Gray QPSK/16-QAM, complex AWGN (Es/N0), TS 38.306 peak rate
  3. Coding             — Pure polynomial-division CRC-16/XMODEM (0x1021) &
                          from-scratch GF(2^8) systematic shortened RS(N, K) (BM+Chien+Forney)
  4. Framing & NetNS    — Strict binary UDP framing (zero cheat flags) & Open5GS ue1/ue2 helpers
"""

from __future__ import annotations


# ===========================================================================
# 1. SCENARIO PARAMETERS
# ===========================================================================

SCENARIOS = {
    "urban_high": {
        "name": "Urban High Dense",
        "description": "Ultra-dense urban plazas (> 1,000 UEs/km²), slow pedestrian flow",
        "ue_density_km2": 1000,
        "blocker_density_rho": 0.150,
        "mean_blocker_velocity_v": 1.1,
        "obstacle_width_w": 0.5,
        "arrival_rate_lambda": 0.344,
        "mean_clear_time_eu": 2.91,
        "mean_outage_time_eb": 0.357,
        "outage_ms": 357,
        "p_block_percent": 10.9,
        "lost_slots": 2856,
        "cell_radius_m": 75,
        "carrier_freq_ghz": 28.0,
        "bandwidth_mhz": 400,
        "baseline_latency_ms": 0.85
    },
    "urban_mild": {
        "name": "Urban Mild Dense",
        "description": "Commercial avenues (≈ 500 UEs/km²), mixed pedestrian/vehicular",
        "ue_density_km2": 500,
        "blocker_density_rho": 0.040,
        "mean_blocker_velocity_v": 2.5,
        "obstacle_width_w": 1.2,
        "arrival_rate_lambda": 0.162,
        "mean_clear_time_eu": 6.17,
        "mean_outage_time_eb": 0.377,
        "outage_ms": 377,
        "p_block_percent": 5.7,
        "lost_slots": 3016,
        "cell_radius_m": 200,
        "carrier_freq_ghz": 28.0,
        "bandwidth_mhz": 200,
        "baseline_latency_ms": 0.90
    },
    "urban_low": {
        "name": "Urban Low Dense",
        "description": "Suburban roads (≈ 100 UEs/km²), moving city vehicles",
        "ue_density_km2": 100,
        "blocker_density_rho": 0.005,
        "mean_blocker_velocity_v": 10.0,
        "obstacle_width_w": 2.0,
        "arrival_rate_lambda": 0.152,
        "mean_clear_time_eu": 6.58,
        "mean_outage_time_eb": 0.157,
        "outage_ms": 157,
        "p_block_percent": 2.3,
        "lost_slots": 1256,
        "cell_radius_m": 400,
        "carrier_freq_ghz": 28.0,
        "bandwidth_mhz": 100,
        "baseline_latency_ms": 0.95
    },
    "rural_high": {
        "name": "Rural High Dense",
        "description": "Agricultural market hubs (≈ 150 UEs/km²), slow farm machinery/cattle",
        "ue_density_km2": 150,
        "blocker_density_rho": 0.030,
        "mean_blocker_velocity_v": 1.2,
        "obstacle_width_w": 1.5,
        "arrival_rate_lambda": 0.098,
        "mean_clear_time_eu": 10.20,
        "mean_outage_time_eb": 0.981,
        "outage_ms": 981,
        "p_block_percent": 8.8,
        "lost_slots": 7848,
        "cell_radius_m": 600,
        "carrier_freq_ghz": 28.0,
        "bandwidth_mhz": 100,
        "baseline_latency_ms": 1.10
    },
    "rural_mild": {
        "name": "Rural Mild Dense",
        "description": "Dispersed rural townships (≈ 50 UEs/km²), mixed vehicular flow",
        "ue_density_km2": 50,
        "blocker_density_rho": 0.005,
        "mean_blocker_velocity_v": 4.0,
        "obstacle_width_w": 1.8,
        "arrival_rate_lambda": 0.058,
        "mean_clear_time_eu": 17.24,
        "mean_outage_time_eb": 0.353,
        "outage_ms": 353,
        "p_block_percent": 2.0,
        "lost_slots": 2824,
        "cell_radius_m": 800,
        "carrier_freq_ghz": 28.0,
        "bandwidth_mhz": 50,
        "baseline_latency_ms": 1.20
    },
    "rural_low": {
        "name": "Rural Low Dense",
        "description": "Open highways and farmland (≈ 10 UEs/km²), high-speed vehicular/trucks",
        "ue_density_km2": 10,
        "blocker_density_rho": 0.0005,
        "mean_blocker_velocity_v": 20.0,
        "obstacle_width_w": 2.4,
        "arrival_rate_lambda": 0.033,
        "mean_clear_time_eu": 30.30,
        "mean_outage_time_eb": 0.094,
        "outage_ms": 94,
        "p_block_percent": 0.31,
        "lost_slots": 752,
        "cell_radius_m": 1500,
        "carrier_freq_ghz": 28.0,
        "bandwidth_mhz": 50,
        "baseline_latency_ms": 1.30
    }
}

SUB6_BASELINE = {
    "carrier_freq_ghz": 3.5,
    "bandwidth_mhz": 40,
    "slot_duration_ms": 0.5,
    "baseline_latency_ms": 12.4,
    "jitter_ms": 1.5,
    "penetration_loss_db": 4.0
}

# ===========================================================================
# 2. PHYSICS & BASEBAND CHANNEL
# ===========================================================================

import numpy as np
from scipy.special import fresnel

C_LIGHT = 299_792_458.0  # m/s


# ---------------------------------------------------------------------------
# 1. Diffraction Physics
# ---------------------------------------------------------------------------

def exact_fresnel_single_edge_loss_db(nu: np.ndarray | float) -> np.ndarray | float:
    """
    Exact single semi-infinite knife-edge diffraction loss in dB.
    nu > 0: shadow region; nu = 0: grazing edge (6.0206 dB); nu < 0: lit region.
    Note: In the lit region (nu < 0), Fresnel ripples produce slight gain (negative loss dB).
    """
    nu_arr = np.asarray(nu, dtype=np.float64)
    s, c = fresnel(nu_arr)
    # Complex field ratio E / E0 = (1 + j)/2 * [(0.5 - C(nu)) - j(0.5 - S(nu))]
    # |E / E0|^2 = 0.5 * [(0.5 - C(nu))^2 + (0.5 - S(nu))^2]
    power_ratio = 0.5 * ((0.5 - c) ** 2 + (0.5 - s) ** 2)
    loss_db = -10.0 * np.log10(np.maximum(power_ratio, 1e-30))
    return float(loss_db) if np.ndim(nu) == 0 else loss_db


def tr38901_single_edge_F_from_nu(nu: np.ndarray | float) -> np.ndarray | float:
    """
    3GPP TR 38.901 Eq. (7.6-22) single-edge diffraction parameter F(nu) in the
    paraxial limit where delta_d = D1 + D2 - r = (lambda / 4) * nu^2.
      F = (1/pi) * arctan( sign(nu) * (pi/2) * sqrt((pi / lambda) * delta_d) )
        = (1/pi) * arctan( (pi * sqrt(pi) / 4) * nu )
    """
    nu_arr = np.asarray(nu, dtype=np.float64)
    F = np.arctan((np.pi * np.sqrt(np.pi) / 4.0) * nu_arr) / np.pi
    return float(F) if np.ndim(nu) == 0 else F


def tr38901_single_edge_loss_db(nu: np.ndarray | float) -> np.ndarray | float:
    """
    Single semi-infinite knife-edge loss in dB using 3GPP TR 38.901's smooth F(nu):
      L_dB = -20 * log10(0.5 - F(nu))
    At nu = 0, F(0) = 0 -> L_dB = -20*log10(0.5) = 6.0206 dB.
    """
    F = tr38901_single_edge_F_from_nu(nu)
    field_mag = np.maximum(0.5 - np.asarray(F), 1e-15)
    loss_db = -20.0 * np.log10(field_mag)
    return float(loss_db) if np.ndim(nu) == 0 else loss_db


def _edge_F_38901(
    d1: float,
    d2: float,
    perp_offset: float,
    shadowed: bool,
    wavelength: float,
) -> float:
    """
    Exact 3GPP TR 38.901 Eq. (7.6-22) F factor for one edge of a screen at
    distances d1 (TX to screen plane) and d2 (screen plane to RX).

    perp_offset: perpendicular distance from the LoS ray to the edge (>= 0).
    shadowed: True if the LoS ray is on the shadow side of this edge (+ sign),
              False if on the lit side (- sign).
    """
    r = d1 + d2
    D1 = np.hypot(d1, perp_offset)
    D2 = np.hypot(d2, perp_offset)
    delta_d = max(0.0, (D1 + D2) - r)
    sign = 1.0 if shadowed else -1.0
    arg = sign * (np.pi / 2.0) * np.sqrt((np.pi / wavelength) * delta_d)
    return float(np.arctan(arg) / np.pi)


def tr38901_4edge_loss_db(
    x_center: float,
    d1: float,
    d2: float,
    freq_hz: float,
    W: float = 0.5,
    H: float = 1.7,
    z_ray: float = 1.2,
    z_bottom: float = 0.0,
) -> float:
    """
    3GPP TR 38.901 Section 7.6.4.1 Model B: 4-edge rectangular screen diffraction loss (dB).

    Coordinate convention (screen plane perpendicular to LoS ray at x=0, z=z_ray):
      - Screen spans horizontally [x_center - W/2, x_center + W/2]
      - Screen spans vertically   [z_bottom, z_bottom + H]
      - LoS ray pierces the screen plane at (x=0, z=z_ray).

    Eq. (7.6-21):
      L_dB = -20 * log10( 1 - (F_h1 + F_h2) * (F_v1 + F_v2) )
    """
    wavelength = C_LIGHT / freq_hz

    x_left = x_center - W / 2.0
    x_right = x_center + W / 2.0
    z_top = z_bottom + H

    # Horizontal edges: ray at x=0 is shadowed by left edge iff x_left <= 0,
    # and shadowed by right edge iff x_right >= 0.
    F_h1 = _edge_F_38901(d1, d2, abs(0.0 - x_left), shadowed=(x_left <= 0.0), wavelength=wavelength)
    F_h2 = _edge_F_38901(d1, d2, abs(x_right - 0.0), shadowed=(x_right >= 0.0), wavelength=wavelength)

    # Vertical edges: ray at z=z_ray is shadowed by bottom edge iff z_bottom <= z_ray,
    # and shadowed by top edge iff z_top >= z_ray.
    F_v1 = _edge_F_38901(d1, d2, abs(z_ray - z_bottom), shadowed=(z_bottom <= z_ray), wavelength=wavelength)
    F_v2 = _edge_F_38901(d1, d2, abs(z_top - z_ray), shadowed=(z_top >= z_ray), wavelength=wavelength)

    attenuation = 1.0 - (F_h1 + F_h2) * (F_v1 + F_v2)
    attenuation = max(attenuation, 1e-12)
    return float(-20.0 * np.log10(attenuation))


# ---------------------------------------------------------------------------
# 2. Baseband Gray Modulation & ML Euclidean Demapping
# ---------------------------------------------------------------------------

# Gray-coded 2-bit PAM levels: 00 -> -3, 01 -> -1, 11 -> +1, 10 -> +3
_GRAY2_TO_PAM4 = np.array([-3.0, -1.0, 3.0, 1.0], dtype=np.float64)
_PAM4_TO_GRAY2 = np.array([0, 1, 3, 2], dtype=np.uint8)  # index for levels [-3, -1, +1, +3]

# Unit-energy 16-QAM normalization: E[I^2 + Q^2] = 5 + 5 = 10 -> scale by 1/sqrt(10)
_QAM16_NORM = 1.0 / np.sqrt(10.0)
_QPSK_NORM = 1.0 / np.sqrt(2.0)

# Build exact 16-point constellation table indexed by 4-bit nibble (b3 b2 b1 b0):
#   I uses (b3, b2), Q uses (b1, b0)
_QAM16_CONSTELLATION = np.empty(16, dtype=np.complex128)
for _nib in range(16):
    _i_bits = (_nib >> 2) & 0x3
    _q_bits = _nib & 0x3
    _QAM16_CONSTELLATION[_nib] = (_GRAY2_TO_PAM4[_i_bits] + 1j * _GRAY2_TO_PAM4[_q_bits]) * _QAM16_NORM

# QPSK constellation indexed by 2-bit symbol (b1 b0): 0 -> -1, 1 -> +1
_QPSK_CONSTELLATION = np.array(
    [(-1 - 1j), (-1 + 1j), (1 - 1j), (1 + 1j)], dtype=np.complex128
) * _QPSK_NORM


def bytes_to_nibbles(data: bytes) -> np.ndarray:
    """Split each byte into [high_nibble, low_nibble] so each 16-QAM symbol maps to half a byte."""
    arr = np.frombuffer(data, dtype=np.uint8)
    high = (arr >> 4) & 0x0F
    low = arr & 0x0F
    out = np.empty(arr.size * 2, dtype=np.uint8)
    out[0::2] = high
    out[1::2] = low
    return out


def nibbles_to_bytes(nibbles: np.ndarray) -> bytes:
    """Recombine [high_nibble, low_nibble] pairs back into bytes."""
    n = np.asarray(nibbles, dtype=np.uint8)
    arr = ((n[0::2] << 4) | (n[1::2] & 0x0F)).astype(np.uint8)
    return arr.tobytes()


def modulate_16qam_bytes(data: bytes) -> np.ndarray:
    """Map bytes -> nibble-aligned unit-energy Gray 16-QAM complex symbols (Es = 1)."""
    nibs = bytes_to_nibbles(data)
    return _QAM16_CONSTELLATION[nibs]


def demap_16qam_to_bytes(rx_symbols: np.ndarray) -> bytes:
    """ML minimum-Euclidean-distance Gray 16-QAM demapper -> bytes."""
    # Because I and Q are orthogonal rectangular PAM-4 grids, exact 2D ML Euclidean
    # demapping is mathematically identical to independent nearest-level I and Q slicing.
    # Verify via 16-point distance or exact threshold slicing (identical, faster for 10^7 bits).
    scaled_i = rx_symbols.real / _QAM16_NORM
    scaled_q = rx_symbols.imag / _QAM16_NORM

    # Decision boundaries for {-3, -1, +1, +3} are {-2, 0, +2}
    idx_i = (scaled_i >= -2.0).astype(np.uint8) + (scaled_i >= 0.0).astype(np.uint8) + (scaled_i >= 2.0).astype(np.uint8)
    idx_q = (scaled_q >= -2.0).astype(np.uint8) + (scaled_q >= 0.0).astype(np.uint8) + (scaled_q >= 2.0).astype(np.uint8)

    gray_i = _PAM4_TO_GRAY2[idx_i]
    gray_q = _PAM4_TO_GRAY2[idx_q]
    nibs = (gray_i << 2) | gray_q
    return nibbles_to_bytes(nibs)


def modulate_qpsk_bits(bits: np.ndarray) -> np.ndarray:
    """Map flat bit array (even length) -> unit-energy Gray QPSK symbols (Es = 1)."""
    b = np.asarray(bits, dtype=np.uint8).reshape(-1, 2)
    idx = (b[:, 0] << 1) | b[:, 1]
    return _QPSK_CONSTELLATION[idx]


def demap_qpsk_to_bits(rx_symbols: np.ndarray) -> np.ndarray:
    """ML minimum-Euclidean-distance QPSK demapper -> flat bit array."""
    b0 = (rx_symbols.real >= 0.0).astype(np.uint8)
    b1 = (rx_symbols.imag >= 0.0).astype(np.uint8)
    out = np.empty(rx_symbols.size * 2, dtype=np.uint8)
    out[0::2] = b0
    out[1::2] = b1
    return out


def modulate_16qam_bits(bits: np.ndarray) -> np.ndarray:
    """Map flat bit array (multiple of 4) -> unit-energy Gray 16-QAM symbols (Es = 1)."""
    b = np.asarray(bits, dtype=np.uint8).reshape(-1, 4)
    nibs = (b[:, 0] << 3) | (b[:, 1] << 2) | (b[:, 2] << 1) | b[:, 3]
    return _QAM16_CONSTELLATION[nibs]


def demap_16qam_to_bits(rx_symbols: np.ndarray) -> np.ndarray:
    """ML minimum-Euclidean-distance Gray 16-QAM demapper -> flat bit array."""
    scaled_i = rx_symbols.real / _QAM16_NORM
    scaled_q = rx_symbols.imag / _QAM16_NORM

    idx_i = (scaled_i >= -2.0).astype(np.uint8) + (scaled_i >= 0.0).astype(np.uint8) + (scaled_i >= 2.0).astype(np.uint8)
    idx_q = (scaled_q >= -2.0).astype(np.uint8) + (scaled_q >= 0.0).astype(np.uint8) + (scaled_q >= 2.0).astype(np.uint8)

    gray_i = _PAM4_TO_GRAY2[idx_i]
    gray_q = _PAM4_TO_GRAY2[idx_q]
    nibs = (gray_i << 2) | gray_q

    out = np.empty((nibs.size, 4), dtype=np.uint8)
    out[:, 0] = (nibs >> 3) & 1
    out[:, 1] = (nibs >> 2) & 1
    out[:, 2] = (nibs >> 1) & 1
    out[:, 3] = nibs & 1
    return out.ravel()


def awgn_channel_es_n0(
    tx_symbols: np.ndarray,
    es_n0_db: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Add complex AWGN to unit-energy symbols (Es = 1) at the given Es/N0 (dB).
    Variance per axis = N0 / 2 -> std per axis = sqrt(N0 / 2).
    """
    es_n0_lin = 10.0 ** (es_n0_db / 10.0)
    n0 = 1.0 / es_n0_lin
    sigma_axis = np.sqrt(n0 / 2.0)
    noise = rng.normal(0.0, sigma_axis, size=tx_symbols.shape) + 1j * rng.normal(
        0.0, sigma_axis, size=tx_symbols.shape
    )
    return tx_symbols + noise


def transmit_bytes_over_channel(
    data: bytes,
    es_n0_db: float,
    rng: np.random.Generator,
) -> bytes:
    """Full baseband chain: bytes -> Gray 16-QAM -> AWGN(Es/N0) -> ML demap -> bytes."""
    tx_syms = modulate_16qam_bytes(data)
    rx_syms = awgn_channel_es_n0(tx_syms, es_n0_db, rng)
    return demap_16qam_to_bytes(rx_syms)


# ---------------------------------------------------------------------------
# 3. Modelled 5G NR Bandwidth, Thermal Noise & Goodput (TS 38.306 Structure)
# ---------------------------------------------------------------------------

NR_BAND_PROFILES = {
    "mmwave": {
        "label": "28 GHz mmWave (FR2)",
        "freq_hz": 28e9,
        "bandwidth_hz": 400e6,
        "scs_khz": 120,
        "n_rb": 264,                      # TS 38.104 FR2 400 MHz @ 120 kHz SCS
        "slot_duration_s": 0.125e-3,
        "overhead": 0.18,                 # TS 38.306 DL FR2 overhead
        "illustrative_latency_ms": 0.85,  # Assumed illustrative value (scenario_params.py)
    },
    "sub6": {
        "label": "3.5 GHz Sub-6 (FR1)",
        "freq_hz": 3.5e9,
        "bandwidth_hz": 40e6,
        "scs_khz": 30,
        "n_rb": 106,                      # TS 38.104 FR1 40 MHz @ 30 kHz SCS
        "slot_duration_s": 0.5e-3,
        "overhead": 0.14,                 # TS 38.306 DL FR1 overhead
        "illustrative_latency_ms": 12.4,  # Assumed illustrative value (scenario_params.py)
    },
}


def thermal_noise_dbm(bandwidth_hz: float, nf_db: float = 7.0) -> float:
    """Thermal noise floor in dBm: -174 dBm/Hz + 10*log10(B) + NF."""
    return float(-174.0 + 10.0 * np.log10(bandwidth_hz) + nf_db)


# 3GPP TS 38.104 Table 5.3.2-2: FR2 max N_RB at 120 kHz SCS
FR2_120KHZ_NRB = {
    50: 32,
    100: 66,
    200: 132,
    400: 264,
}


def nr_modelled_peak_rate_mbps(
    band: str,
    mod_bits: int = 4,
    code_rate: float = 18.0 / 24.0,
    n_layers: int = 1,
    bandwidth_mhz: int | None = None,
) -> float:
    """
    Single-layer peak net payload rate (Mbps) modelled from the 3GPP TS 38.306
    structure, substituting our RS+CRC net payload rate (default 18/24 = 0.75)
    for NR's LDPC code rate:
      R_peak = n_layers * 12 * N_RB * 14 * mod_bits * code_rate * (1 - OH) / T_slot
    """
    p = NR_BAND_PROFILES[band]
    n_rb = p["n_rb"]
    if band == "mmwave" and bandwidth_mhz in FR2_120KHZ_NRB:
        n_rb = FR2_120KHZ_NRB[bandwidth_mhz]
    bits_per_slot = (
        n_layers * 12 * n_rb * 14 * mod_bits * code_rate * (1.0 - p["overhead"])
    )
    return float((bits_per_slot / p["slot_duration_s"]) / 1e6)

# ===========================================================================
# 3. CRC-16/XMODEM & GF(2^8) REED-SOLOMON CODING
# ===========================================================================

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 1. Pure Polynomial-Division CRC-16 (G(x) = x^16 + x^12 + x^5 + 1)
# ---------------------------------------------------------------------------

CRC16_POLY = 0x1021


def crc16_remainder(data: bytes) -> int:
    """
    Pure bit-by-bit polynomial long division over GF(2):
      Computes D(x) * x^16 mod G(x)  when called on message M,
      or (M(x) * x^16 + CRC(x)) mod G(x) == 0 when called on M || CRC.
    """
    rem = 0x0000
    for byte in data:
        rem ^= byte << 8
        for _ in range(8):
            if rem & 0x8000:
                rem = ((rem << 1) ^ CRC16_POLY) & 0xFFFF
            else:
                rem = (rem << 1) & 0xFFFF
    return rem


def crc16_append(payload: bytes) -> bytes:
    """Return payload || big-endian 2-byte CRC-16."""
    crc = crc16_remainder(payload)
    return payload + crc.to_bytes(2, "big")


def crc16_verify(payload_with_crc: bytes) -> tuple[bool, int]:
    """
    Verify (M(x) * x^16 + CRC(x)) mod G(x) == 0x0000.
    Rejects empty/truncated inputs (< 3 bytes: requires >= 1 payload byte + 2 CRC bytes).
    Returns (passed, remainder).
    """
    if len(payload_with_crc) < 3:
        return False, 0xFFFF
    rem = crc16_remainder(payload_with_crc)
    return (rem == 0x0000), rem


# ---------------------------------------------------------------------------
# 2. GF(2^8) Finite Field Arithmetic (primitive poly 0x11D, alpha = 2)
# ---------------------------------------------------------------------------

_GF_PRIM = 0x11D
_GF_EXP = [0] * 512
_GF_LOG = [0] * 256

_x = 1
for _i in range(255):
    _GF_EXP[_i] = _x
    _GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= _GF_PRIM
for _i in range(255, 512):
    _GF_EXP[_i] = _GF_EXP[_i - 255]


def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def gf_div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("GF(2^8) division by zero")
    if a == 0:
        return 0
    return _GF_EXP[(_GF_LOG[a] - _GF_LOG[b]) % 255]


def gf_pow(a: int, power: int) -> int:
    if a == 0:
        return 1 if power == 0 else 0
    return _GF_EXP[(_GF_LOG[a] * power) % 255]


def gf_inv(a: int) -> int:
    if a == 0:
        raise ZeroDivisionError("GF(2^8) inverse of zero")
    return _GF_EXP[255 - _GF_LOG[a]]


def gf_poly_mul(p: list[int], q: list[int]) -> list[int]:
    """Multiply polynomials in highest-degree-first order."""
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        if a == 0:
            continue
        for j, b in enumerate(q):
            out[i + j] ^= gf_mul(a, b)
    return out


def gf_poly_eval(poly: list[int], x: int) -> int:
    """Evaluate highest-degree-first polynomial at x in GF(2^8) using Horner's rule."""
    acc = 0
    for coeff in poly:
        acc = gf_mul(acc, x) ^ coeff
    return acc


def rs_generator_poly(nsym: int) -> list[int]:
    """g(x) = prod_{j=0}^{nsym-1} (x - alpha^j), highest-degree first."""
    g = [1]
    for j in range(nsym):
        g = gf_poly_mul(g, [1, _GF_EXP[j]])
    return g


# ---------------------------------------------------------------------------
# 3. Systematic Shortened RS(N, K) Encoder & Berlekamp-Massey + Forney Decoder
# ---------------------------------------------------------------------------

def rs_encode(data: bytes, nsym: int = 4) -> bytes:
    """
    Systematic Reed-Solomon encoding over GF(2^8).
    Requires even nsym >= 2, len(data) >= 1, and N = len(data) + nsym <= 255.
    First K = len(data) bytes are unchanged; last nsym bytes are parity.
    """
    if nsym < 2 or nsym % 2 != 0:
        raise ValueError(f"Invalid nsym={nsym} (must be even and >= 2)")
    if len(data) < 1:
        raise ValueError("Data to RS-encode must be non-empty")
    if len(data) + nsym > 255:
        raise ValueError(f"Codeword length {len(data) + nsym} exceeds 255")
    gen = rs_generator_poly(nsym)
    buf = list(data) + [0] * nsym
    for i in range(len(data)):
        coef = buf[i]
        if coef != 0:
            for j in range(1, len(gen)):
                buf[i + j] ^= gf_mul(gen[j], coef)
    return bytes(data) + bytes(buf[len(data):])


def rs_syndromes(codeword: bytes, nsym: int = 4) -> list[int]:
    """Compute S_j = r(alpha^j) over GF(2^8) for j = 0, ..., nsym - 1."""
    poly = list(codeword)
    return [gf_poly_eval(poly, _GF_EXP[j]) for j in range(nsym)]


@dataclass
class RSDecodeResult:
    success: bool
    message: bytes          # K-byte data portion (payload + CRC if CRC is inside RS)
    codeword: bytes         # Full N-byte codeword (repaired if success)
    syndromes: list[int]
    errors_corrected: int
    error_positions: list[int]
    parity_only: bool       # True iff errors occurred only in parity bytes (pos >= K)
    reason: str


def _berlekamp_massey(syndromes: list[int]) -> list[int]:
    """
    Compute error locator polynomial Lambda(x) = 1 + L1*x + ... + Lv*x^v
    (returned in LOWEST-degree-first order: [1, L1, ..., Lv]).
    """
    nsym = len(syndromes)
    C = [1]  # current error locator
    B = [1]  # previous error locator
    L = 0    # current number of assumed errors
    m = 1    # steps since last update
    b = 1    # previous discrepancy

    for n in range(nsym):
        # Discrepancy d = S_n + sum_{i=1..L} C_i * S_{n-i}
        d = syndromes[n]
        for i in range(1, L + 1):
            d ^= gf_mul(C[i], syndromes[n - i])

        if d == 0:
            m += 1
        else:
            T = list(C)
            coef = gf_div(d, b)
            # C(x) <- C(x) - coef * x^m * B(x)
            shifted_B = [0] * m + [gf_mul(coef, x) for x in B]
            if len(shifted_B) > len(C):
                C.extend([0] * (len(shifted_B) - len(C)))
            for i in range(len(shifted_B)):
                C[i] ^= shifted_B[i]

            if 2 * L <= n:
                L = n + 1 - L
                B = T
                b = d
                m = 1
            else:
                m += 1

    # Strip trailing zeros
    while len(C) > 1 and C[-1] == 0:
        C.pop()
    return C


def rs_decode(codeword: bytes, nsym: int = 4) -> RSDecodeResult:
    """
    Full GF(2^8) Reed-Solomon decoder:
      1. Syndromes S_j = r(alpha^j)
      2. Berlekamp-Massey -> error locator Lambda(x)
      3. Chien search -> error positions within shortened range [0, N-1]
      4. Forney's algorithm -> error magnitudes
      5. Re-verify all syndromes == 0
    """
    n = len(codeword)
    if nsym < 2 or nsym % 2 != 0:
        return RSDecodeResult(
            success=False,
            message=b"",
            codeword=codeword,
            syndromes=[],
            errors_corrected=0,
            error_positions=[],
            parity_only=False,
            reason=f"invalid nsym={nsym} (must be even and >= 2)",
        )
    if n <= nsym or n > 255:
        return RSDecodeResult(
            success=False,
            message=b"",
            codeword=codeword,
            syndromes=[],
            errors_corrected=0,
            error_positions=[],
            parity_only=False,
            reason=f"invalid codeword length {n} for nsym={nsym} (must be in [{nsym + 1}, 255])",
        )
    k = n - nsym
    t_max = nsym // 2
    syn = rs_syndromes(codeword, nsym)

    if max(syn) == 0:
        return RSDecodeResult(
            success=True,
            message=codeword[:k],
            codeword=codeword,
            syndromes=syn,
            errors_corrected=0,
            error_positions=[],
            parity_only=False,
            reason="clean",
        )

    # Berlekamp-Massey -> Lambda(x) in lowest-degree-first order
    lam = _berlekamp_massey(syn)
    num_err = len(lam) - 1
    if num_err == 0 or num_err > t_max:
        return RSDecodeResult(
            success=False,
            message=codeword[:k],
            codeword=codeword,
            syndromes=syn,
            errors_corrected=0,
            error_positions=[],
            parity_only=False,
            reason=f"uncorrectable (locator degree {num_err} > t={t_max})",
        )

    # Chien search: codeword index pos corresponds to power p = n - 1 - pos,
    # locator X_k = alpha^p, so root of Lambda(x) is X_k^{-1} = alpha^{-p}.
    lam_high_first = list(reversed(lam))
    err_positions: list[int] = []
    err_powers: list[int] = []
    for pos in range(n):
        p = n - 1 - pos
        x_inv = _GF_EXP[(255 - p) % 255]
        if gf_poly_eval(lam_high_first, x_inv) == 0:
            err_positions.append(pos)
            err_powers.append(p)

    # Critical for shortened RS: all num_err roots must land inside [0, n-1]
    if len(err_positions) != num_err:
        return RSDecodeResult(
            success=False,
            message=codeword[:k],
            codeword=codeword,
            syndromes=syn,
            errors_corrected=0,
            error_positions=[],
            parity_only=False,
            reason=f"uncorrectable (only {len(err_positions)}/{num_err} roots in shortened block)",
        )

    # Error evaluator polynomial Omega(x) = S(x) * Lambda(x) mod x^{nsym}
    # Both S(x) and Lambda(x) are lowest-degree first here
    omega = [0] * nsym
    for i in range(nsym):
        acc = 0
        for j in range(min(i + 1, len(lam))):
            acc ^= gf_mul(syn[i - j], lam[j])
        omega[i] = acc

    # Formal derivative Lambda'(x) in GF(2^8): even-index terms vanish in char 2
    # Lambda'(x) = sum_{i odd} lam[i] * x^{i-1}
    lam_deriv = [lam[i] if (i % 2 == 1) else 0 for i in range(1, len(lam))]
    # Evaluate lowest-degree-first helper
    def eval_low_first(poly: list[int], x: int) -> int:
        res = 0
        xp = 1
        for c in poly:
            if c:
                res ^= gf_mul(c, xp)
            xp = gf_mul(xp, x)
        return res

    # Forney's algorithm (for first consecutive root b = 0, i.e., alpha^0 = 1):
    #   e_k = X_k * Omega(X_k^{-1}) / Lambda'(X_k^{-1})
    repaired = bytearray(codeword)
    for pos, p in zip(err_positions, err_powers):
        X_k = _GF_EXP[p % 255]
        X_k_inv = _GF_EXP[(255 - p) % 255]
        num = gf_mul(X_k, eval_low_first(omega, X_k_inv))
        den = eval_low_first(lam_deriv, X_k_inv)
        if den == 0:
            return RSDecodeResult(
                success=False,
                message=codeword[:k],
                codeword=codeword,
                syndromes=syn,
                errors_corrected=0,
                error_positions=[],
                parity_only=False,
                reason="forney zero denominator",
            )
        mag = gf_div(num, den)
        repaired[pos] ^= mag

    repaired_bytes = bytes(repaired)
    check_syn = rs_syndromes(repaired_bytes, nsym)
    if max(check_syn) != 0:
        return RSDecodeResult(
            success=False,
            message=codeword[:k],
            codeword=codeword,
            syndromes=syn,
            errors_corrected=0,
            error_positions=[],
            parity_only=False,
            reason="post-repair syndrome non-zero",
        )

    parity_only = all(pos >= k for pos in err_positions)
    return RSDecodeResult(
        success=True,
        message=repaired_bytes[:k],
        codeword=repaired_bytes,
        syndromes=syn,
        errors_corrected=len(err_positions),
        error_positions=err_positions,
        parity_only=parity_only,
        reason="parity-only fix" if parity_only else f"repaired {len(err_positions)} byte(s)",
    )

# ===========================================================================
# 4. STRICT UDP FRAMING & OPEN5GS NETNS HELPERS
# ===========================================================================

import os
import re
import struct
import subprocess
import sys

HEADER_FMT = "!2sIHhhBBBB"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
MAGIC = b"5G"
LINK_MMWAVE = 0
LINK_SUB6 = 1
FLAG_EOS = 0x01

# Feedback packet (Program 3 -> Program 1): magic(2s), seq(I), code(B)
FB_FMT = "!2sIB"
FB_SIZE = struct.calcsize(FB_FMT)
FB_MAGIC = b"FB"
FB_ACK_MMW = 1
FB_NACK_MMW = 2
FB_ACK_SUB6 = 3
FB_NACK_SUB6 = 4
_VALID_FB_CODES = (FB_ACK_MMW, FB_NACK_MMW, FB_ACK_SUB6, FB_NACK_SUB6)


def pack_feedback(seq: int, code: int) -> bytes:
    if code not in _VALID_FB_CODES:
        raise ValueError(f"Unsupported feedback code: {code}")
    return struct.pack(FB_FMT, FB_MAGIC, seq, code)


def unpack_feedback(packet: bytes) -> tuple[int, int]:
    if len(packet) != FB_SIZE:
        raise ValueError(f"Feedback packet length mismatch: got {len(packet)}, expected {FB_SIZE}")
    magic, seq, code = struct.unpack(FB_FMT, packet)
    if magic != FB_MAGIC:
        raise ValueError(f"Bad feedback magic: {magic!r}")
    if code not in _VALID_FB_CODES:
        raise ValueError(f"Unsupported feedback code: {code}")
    return seq, code


def pack_frame(
    seq: int,
    step_idx: int,
    x_m: float,
    snr_db: float,
    link_id: int,
    rs_nsym: int,
    codeword: bytes,
    eos: bool = False,
) -> bytes:
    x_mm = int(round(x_m * 1000.0))
    snr_cdb = int(round(snr_db * 100.0))
    if not (-32768 <= x_mm <= 32767):
        raise ValueError(f"x_m={x_m} out of int16 millimeter range [-32.768, 32.767]")
    if not (-32768 <= snr_cdb <= 32767):
        raise ValueError(f"snr_db={snr_db} out of int16 centi-dB range [-327.68, 327.67]")
    flags = FLAG_EOS if eos else 0
    hdr = struct.pack(
        HEADER_FMT,
        MAGIC,
        seq,
        step_idx,
        x_mm,
        snr_cdb,
        link_id,
        rs_nsym,
        len(codeword),
        flags,
    )
    return hdr + codeword


def unpack_frame(packet: bytes) -> dict:
    if len(packet) < HEADER_SIZE:
        raise ValueError(f"Truncated header: got {len(packet)} bytes, need >= {HEADER_SIZE}")
    magic, seq, step_idx, x_mm, snr_cdb, link_id, rs_nsym, cw_len, flags = struct.unpack(
        HEADER_FMT, packet[:HEADER_SIZE]
    )
    if magic != MAGIC:
        raise ValueError(f"Bad magic: {magic!r}")
    if link_id not in (LINK_MMWAVE, LINK_SUB6):
        raise ValueError(f"Unsupported link_id: {link_id}")
    if flags & ~FLAG_EOS:
        raise ValueError(f"Unsupported frame flags: 0x{flags:02X}")
    expected_len = HEADER_SIZE + cw_len
    if len(packet) != expected_len:
        raise ValueError(
            f"Packet length mismatch: got {len(packet)} bytes, header declares {expected_len} (cw_len={cw_len})"
        )
    eos = bool(flags & FLAG_EOS)
    if not eos:
        if rs_nsym < 2 or rs_nsym % 2 != 0:
            raise ValueError(f"Invalid rs_nsym={rs_nsym} (must be even and >= 2)")
        if cw_len <= rs_nsym + 2 or cw_len > 255:
            raise ValueError(f"Invalid cw_len={cw_len} for rs_nsym={rs_nsym} (must be in [{rs_nsym + 3}, 255])")
    codeword = packet[HEADER_SIZE:expected_len]
    return {
        "seq": seq,
        "step_idx": step_idx,
        "x_m": x_mm / 1000.0,
        "snr_db": snr_cdb / 100.0,
        "link_id": link_id,
        "rs_nsym": rs_nsym,
        "codeword": codeword,
        "eos": eos,
    }


def detect_ue_ips() -> tuple[str | None, str | None]:
    """Read uesimtun0 IPv4 addresses inside UERANSIM namespaces ue1 and ue2."""
    ips: list[str | None] = []
    for ns in ("ue1", "ue2"):
        ip_found = None
        try:
            out = subprocess.check_output(
                ["ip", "netns", "exec", ns, "ip", "-4", "addr", "show", "dev", "uesimtun0"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            m = re.search(r"inet\s+([0-9.]+)", out)
            if m:
                ip_found = m.group(1)
        except Exception:
            pass
        ips.append(ip_found)
    return ips[0], ips[1]


def enter_netns(ns_name: str) -> None:
    """Attach current Python process to /var/run/netns/<ns_name> via os.setns."""
    ns_path = f"/var/run/netns/{ns_name}"
    if not os.path.exists(ns_path):
        print(f"[!] Error: Network namespace {ns_path} not found.")
        print("    Run: sudo ./start_5g_stack.sh  (or pass --loopback for offline test)")
        sys.exit(1)
    if os.geteuid() != 0:
        print(f"[!] Error: Root privileges required to enter netns {ns_name}.")
        print("    Run with sudo, or pass --loopback for offline test.")
        sys.exit(1)
    with open(ns_path) as f:
        os.setns(f.fileno(), os.CLONE_NEWNET)

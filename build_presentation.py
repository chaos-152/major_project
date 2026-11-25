#!/usr/bin/env python3
"""
Builds the 10-slide widescreen (16:9) viva presentation:
  /home/realfifth/UERANSIM/emulation/Physics_to_Bits_5G_Error_Model.pptx
using verified numbers and plots from validate_physics_to_bits.py.
"""

from __future__ import annotations

import os
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

BASE_DIR = "/home/realfifth/UERANSIM/emulation"
PLOT_DIR = os.path.join(BASE_DIR, "plots")
OUT_PPTX = os.path.join(BASE_DIR, "Physics_to_Bits_5G_Error_Model.pptx")

# Palette: Deep Navy + Slate + Cyan/Teal + Warm Amber + Clean White
BG_DARK = RGBColor(0x0B, 0x13, 0x2B)      # Deep navy (title slide)
BG_LIGHT = RGBColor(0xF8, 0xFA, 0xFC)     # Clean light slate (content slides)
CARD_BG = RGBColor(0xFF, 0xFF, 0xFF)      # White card
CARD_ALT = RGBColor(0xF1, 0xF5, 0xF9)     # Subtle cool gray card
TERM_BG = RGBColor(0x0F, 0x17, 0x2A)      # Terminal dark slate
NAVY = RGBColor(0x0F, 0x17, 0x2A)         # Primary dark text / headers
SLATE = RGBColor(0x33, 0x41, 0x55)        # Body text
MUTED = RGBColor(0x64, 0x74, 0x8B)        # Captions / footers
CYAN = RGBColor(0x02, 0x84, 0xC7)         # Primary accent (blue/cyan)
TEAL = RGBColor(0x0D, 0x94, 0x88)         # Secondary accent (green/teal)
AMBER = RGBColor(0xD9, 0x77, 0x06)        # Highlight / Sub-6 accent
RED = RGBColor(0xDC, 0x26, 0x26)          # Error / mmWave drop accent
BORDER = RGBColor(0xCB, 0xD5, 0xE1)       # Subtle card border
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_CYAN = RGBColor(0x38, 0xBD, 0xF8)
TERM_GREEN = RGBColor(0x4A, 0xDE, 0x80)
TERM_RED = RGBColor(0xF8, 0x71, 0x71)
TERM_YELLOW = RGBColor(0xFA, 0xCC, 0x15)
TERM_CYAN = RGBColor(0x67, 0xE8, 0xF9)
TERM_TEXT = RGBColor(0xE2, 0xE8, 0xF0)

FONT_MAIN = "DejaVu Sans"
FONT_MONO = "DejaVu Sans Mono"


def set_slide_bg(slide, color: RGBColor) -> None:
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_header(slide, title: str, subtitle: str, slide_num: int) -> None:
    set_slide_bg(slide, BG_LIGHT)
    # Top accent bar
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = CYAN
    bar.line.fill.background()

    # Title
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.25), Inches(11.5), Inches(0.55))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.text = title
    p.font.name = FONT_MAIN
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = NAVY

    # Subtitle
    sb = slide.shapes.add_textbox(Inches(0.6), Inches(0.80), Inches(11.8), Inches(0.35))
    stf = sb.text_frame
    stf.word_wrap = True
    stf.margin_left = stf.margin_top = stf.margin_right = stf.margin_bottom = 0
    sp = stf.paragraphs[0]
    sp.text = subtitle
    sp.font.name = FONT_MAIN
    sp.font.size = Pt(12.5)
    sp.font.color.rgb = MUTED

    # Divider line
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.20), Inches(12.133), Inches(0.015))
    line.fill.solid()
    line.fill.fore_color.rgb = BORDER
    line.line.fill.background()

    # Footer
    fb = slide.shapes.add_textbox(Inches(0.6), Inches(7.12), Inches(10.0), Inches(0.28))
    ftf = fb.text_frame
    ftf.margin_left = ftf.margin_top = ftf.margin_right = ftf.margin_bottom = 0
    fp = ftf.paragraphs[0]
    fp.text = "Physics-to-Bits 5G Error Model & Hybrid Resilience  |  Open5GS + UERANSIM"
    fp.font.name = FONT_MAIN
    fp.font.size = Pt(9.5)
    fp.font.color.rgb = MUTED

    nb = slide.shapes.add_textbox(Inches(11.8), Inches(7.12), Inches(0.93), Inches(0.28))
    ntf = nb.text_frame
    ntf.margin_left = ntf.margin_top = ntf.margin_right = ntf.margin_bottom = 0
    np_ = ntf.paragraphs[0]
    np_.alignment = PP_ALIGN.RIGHT
    np_.text = f"{slide_num} / 10"
    np_.font.name = FONT_MAIN
    np_.font.size = Pt(9.5)
    np_.font.bold = True
    np_.font.color.rgb = MUTED


def add_card(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    title: str = "",
    accent: RGBColor | None = None,
    fill_color: RGBColor = CARD_BG,
):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.adjustments[0] = 0.03
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.color.rgb = BORDER
    shape.line.width = Pt(1)

    if accent is not None:
        strip = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(0.08), Inches(height)
        )
        strip.fill.solid()
        strip.fill.fore_color.rgb = accent
        strip.line.fill.background()

    if title:
        tb = slide.shapes.add_textbox(
            Inches(left + 0.22), Inches(top + 0.14), Inches(width - 0.35), Inches(0.38)
        )
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = FONT_MAIN
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = accent if accent is not None else NAVY
    return shape


def add_bullets(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    items: list[tuple[str, str]],
    font_size: float = 11.5,
    space_after: float = 6,
    text_color: RGBColor = SLATE,
) -> None:
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    for idx, (bold_prefix, rest) in enumerate(items):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        p.line_spacing = 1.18
        r0 = p.add_run()
        r0.text = "• "
        r0.font.name = FONT_MAIN
        r0.font.size = Pt(font_size)
        r0.font.bold = True
        r0.font.color.rgb = CYAN
        if bold_prefix:
            r1 = p.add_run()
            r1.text = bold_prefix + " "
            r1.font.name = FONT_MAIN
            r1.font.size = Pt(font_size)
            r1.font.bold = True
            r1.font.color.rgb = NAVY
        r2 = p.add_run()
        r2.text = rest
        r2.font.name = FONT_MAIN
        r2.font.size = Pt(font_size)
        r2.font.color.rgb = text_color


def add_table(slide, left: float, top: float, width: float, height: float, headers: list[str], rows: list[list[str]], col_widths: list[float] | None = None, font_size: float = 10.5):
    tbl_shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(left), Inches(top), Inches(width), Inches(height))
    tbl = tbl_shape.table
    if col_widths:
        for i, w in enumerate(col_widths):
            tbl.columns[i].width = Inches(w)

    for c, h in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.name = FONT_MAIN
        p.font.size = Pt(font_size)
        p.font.bold = True
        p.font.color.rgb = WHITE

    for r_idx, row in enumerate(rows):
        bg = CARD_BG if r_idx % 2 == 0 else CARD_ALT
        for c, val in enumerate(row):
            cell = tbl.cell(r_idx + 1, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.name = FONT_MAIN
            p.font.size = Pt(font_size)
            p.font.bold = (c == 0)
            p.font.color.rgb = NAVY if c == 0 else SLATE
    return tbl_shape


def build() -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: TITLE SLIDE
    # =========================================================================
    s1 = prs.slides.add_slide(blank)
    set_slide_bg(s1, BG_DARK)

    # Accent vertical strip & decorative glow bar
    accent_bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.85), Inches(1.55), Inches(0.10), Inches(3.85))
    accent_bar.fill.solid()
    accent_bar.fill.fore_color.rgb = LIGHT_CYAN
    accent_bar.line.fill.background()

    # Eyebrow tag
    pill = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.2), Inches(1.55), Inches(4.7), Inches(0.42))
    pill.adjustments[0] = 0.5
    pill.fill.solid()
    pill.fill.fore_color.rgb = RGBColor(0x1E, 0x29, 0x3B)
    pill.line.color.rgb = LIGHT_CYAN
    ptf = pill.text_frame
    pp = ptf.paragraphs[0]
    pp.alignment = PP_ALIGN.CENTER
    pp.text = "5G NR CHANNEL & ERROR RESILIENCE  |  OPEN5GS + UERANSIM"
    pp.font.name = FONT_MAIN
    pp.font.size = Pt(10.5)
    pp.font.bold = True
    pp.font.color.rgb = LIGHT_CYAN

    # Main Title
    tb = s1.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(11.0), Inches(1.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Physics-to-Bits 5G Error Model\n& Hybrid Resilience Architecture"
    p.font.name = FONT_MAIN
    p.font.size = Pt(38)
    p.font.bold = True
    p.font.color.rgb = WHITE

    # Subtitle
    sb = s1.shapes.add_textbox(Inches(1.2), Inches(4.05), Inches(10.6), Inches(1.1))
    stf = sb.text_frame
    stf.word_wrap = True
    sp = stf.paragraphs[0]
    sp.text = (
        "3GPP TR 38.901 4-Edge Diffraction, Unit-Energy Gray 16-QAM + AWGN, "
        "From-Scratch GF(2⁸) Reed-Solomon Repair, and Stop-and-Wait Sub-6 ARQ Fallback"
    )
    sp.font.name = FONT_MAIN
    sp.font.size = Pt(16)
    sp.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)

    # Bottom KPI badges
    badges = [
        ("28 GHz vs 3.5 GHz", "Same 38.901 diffraction model (8× λ ratio)"),
        ("GF(2⁸) RS(24, 20)", "BM + Chien + Forney + CRC-16 gate"),
        ("0.19% Controlled FER", "41,000 frames (5 seeds), down from 29.47%"),
    ]
    for i, (head, desc) in enumerate(badges):
        bx = 1.2 + i * 3.75
        card = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(bx), Inches(5.55), Inches(3.5), Inches(1.05))
        card.adjustments[0] = 0.08
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(0x16, 0x22, 0x3D)
        card.line.color.rgb = RGBColor(0x33, 0x41, 0x55)
        tbox = s1.shapes.add_textbox(Inches(bx + 0.18), Inches(5.68), Inches(3.15), Inches(0.85))
        ttf = tbox.text_frame
        ttf.word_wrap = True
        p1 = ttf.paragraphs[0]
        p1.text = head
        p1.font.name = FONT_MAIN
        p1.font.size = Pt(14)
        p1.font.bold = True
        p1.font.color.rgb = LIGHT_CYAN
        p2 = ttf.add_paragraph()
        p2.space_before = Pt(3)
        p2.text = desc
        p2.font.name = FONT_MAIN
        p2.font.size = Pt(10.5)
        p2.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)

    # =========================================================================
    # SLIDE 2: PROBLEM STATEMENT & SYSTEM BOUNDARY
    # =========================================================================
    s2 = prs.slides.add_slide(blank)
    add_header(s2, "Problem Statement & System Boundary", "Replacing synthetic IP packet-loss coin-flips with physics-driven bit corruption over a real 5G core", 2)

    add_card(s2, 0.6, 1.45, 5.85, 5.35, "Why Standard Testbed Impairments Fall Short", accent=RED)
    add_bullets(s2, 0.85, 2.02, 5.35, 4.5, [
        ("No RF PHY in UERANSIM/Open5GS:", "UERANSIM emulates 3GPP NAS/NGAP/GTP-U tunnels cleanly, but has no physical radio channel or baseband modem."),
        ("Synthetic tc netem drops are unphysical:", "Flat IP loss (e.g. netem loss 20%) ignores carrier frequency, blocker width, diffraction geometry, and constellation boundaries."),
        ("No bit-level error visibility:", "In production 5G, MAC/RLC CRC + HARQ stop corrupted transport blocks before IP—hiding how PHY bit flips actually happen and get repaired."),
        ("The core question:", "How do we derive genuine bit flips from electromagnetic physics and prove mathematically that FEC + Sub-6 fallback rescues them?"),
    ], font_size=12, space_after=10)

    add_card(s2, 6.85, 1.45, 5.88, 5.35, "Our Solution & Honest Architectural Boundary", accent=TEAL)
    add_bullets(s2, 7.1, 2.02, 5.4, 4.5, [
        ("App-layer PHY/channel emulator:", "Channel corruption is computed from 3GPP TR 38.901 diffraction + Gray 16-QAM + AWGN on the encoded codeword inside UE 1 before UDP transmission."),
        ("Real 5G Core user plane:", "Packets traverse isolated Linux namespaces ue1 → uesimtun0 → nr-ue → nr-gnb → Open5GS UPF (GTP-U UDP 2152) → ue2:uesimtun0."),
        ("Two-tier hybrid resilience:", "Grazing errors (≤2 bytes) are repaired algebraically on 28 GHz via GF(2⁸) RS(24, 20); deep blockage triggers NACK → 3.5 GHz Sub-6 retransmission."),
        ("Explicit scope boundary:", "Transport headers and ACK/NACK frames sit outside the AWGN channel; this is a physics-informed emulator on a 5G testbed, not an NR PHY implementation."),
    ], font_size=12, space_after=10)

    # =========================================================================
    # SLIDE 3: THE 5-LINK PHYSICS-TO-BITS CHAIN
    # =========================================================================
    s3 = prs.slides.add_slide(blank)
    add_header(s3, "The 5-Link Physics-to-Bits Chain", "Every flipped bit traces deterministically from blocker geometry through complex baseband IQ demapping", 3)

    links = [
        ("1. Geometry", "Blocker screen W×H\n(W=0.5m, H=1.7m)\nd₁=1.5m, d₂=10.0m\nOffset x(t)", CYAN),
        ("2. Diffraction", "3GPP TR 38.901\nModel B (4 edges)\nSame eq. for 28 GHz\n& 3.5 GHz", TEAL),
        ("3. SNR Collapse", "Es/N0(x) =\n22.0 dB − L(x)\nU-shaped SNR;\n∩-shaped FER", AMBER),
        ("4. Gray 16-QAM", "Nibble-aligned\nUnit energy Es=1\nAWGN per axis:\nVar = N0/2", CYAN),
        ("5. ML Demap", "Min Euclidean dist.\n±2, 0 / √10 slices\nNatural 1-bit flips\n→ RS byte errors", RED),
    ]
    for i, (hdr, body, col) in enumerate(links):
        lx = 0.6 + i * 2.48
        add_card(s3, lx, 1.55, 2.22, 2.35, hdr, accent=col)
        tb = s3.shapes.add_textbox(Inches(lx + 0.18), Inches(2.10), Inches(1.92), Inches(1.65))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = body
        p.font.name = FONT_MAIN
        p.font.size = Pt(11.5)
        p.font.color.rgb = SLATE
        p.line_spacing = 1.25
        if i < 4:
            arr = s3.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(lx + 2.25), Inches(2.55), Inches(0.20), Inches(0.28))
            arr.fill.solid()
            arr.fill.fore_color.rgb = MUTED
            arr.line.fill.background()

    # Key Equations card
    add_card(s3, 0.6, 4.20, 12.13, 2.65, "Core Mathematical Equations (physics_channel.py)", accent=NAVY, fill_color=CARD_ALT)
    eq_items = [
        ("4-Edge Screen Loss (3GPP TR 38.901 Eq. 7.6-21/22):", "F = (1/π) arctan( ± (π/2) √((π/λ)(D₁ + D₂ − r)) ),   L_dB = −20 log₁₀( 1 − (Fh₁ + Fh₂)(Fv₁ + Fv₂) )"),
        ("SNR & Baseband Noise Scaling:", "Es/N0 = Eb/N0 + 6.02 dB (uncoded 16-QAM);   N₀ = 1 / (Es/N0)_lin;   σ_I = σ_Q = √(N₀ / 2)   for Es = 1 (levels ±1, ±3 scaled by 1/√10)"),
        ("Nibble-to-Byte Alignment:", "Each 8-bit RS symbol splits into 2 Gray 16-QAM nibbles (4 bits/sym) → a single IQ symbol error corrupts at most 1 RS byte."),
        ("Exact Fresnel Reference Check:", "Single semi-infinite knife-edge at ν = 0 gives exactly 6.0206 dB; 38.901 matches within 0.19 dB in shadow (3.03 dB lit-side ripple gap)."),
    ]
    add_bullets(s3, 0.85, 4.72, 11.6, 2.0, eq_items, font_size=11.5, space_after=7)

    # =========================================================================
    # SLIDE 4: WHY 28 GHz mmWave vs 3.5 GHz Sub-6 MATTERS
    # =========================================================================
    s4 = prs.slides.add_slide(blank)
    add_header(s4, "Why 28 GHz mmWave vs. 3.5 GHz Sub-6 Matters", "An 8× wavelength difference drives deep mmWave shadowing vs. mild Sub-6 diffraction", 4)

    headers = ["Metric", "28 GHz mmWave (FR2)", "3.5 GHz Sub-6 (FR1)"]
    rows = [
        ["Wavelength (λ = c/f)", "10.7 mm", "85.7 mm (8× larger)"],
        ["0.5 m Pedestrian (urban_high)", "~47λ → 14.09 dB loss", "~5.8λ → 6.46 dB loss"],
        ["2.4 m Truck (rural_low)", "~224λ → 21.20 dB loss", "~28λ → 12.66 dB loss"],
        ["Channel Bandwidth / SCS", "400 MHz / 120 kHz (264 RB)", "40 MHz / 30 kHz (106 RB)"],
        ["Thermal Noise Floor (NF=7 dB)", "−81.0 dBm (+10 dB)", "−91.0 dBm"],
        ["Modelled Peak Rate (TS 38.306*)", "872.8 Mbps", "91.9 Mbps (~9.5× slower)"],
    ]
    add_table(s4, 0.6, 1.48, 6.25, 3.65, headers, rows, col_widths=[2.45, 1.90, 1.90], font_size=10.5)

    add_card(s4, 0.6, 5.32, 6.25, 1.55, "Key Takeaway & Honest Link-Budget Note", accent=AMBER)
    add_bullets(s4, 0.82, 5.78, 5.85, 1.0, [
        ("Trade-off:", "mmWave delivers ~9.5× higher modelled peak rate but collapses behind a 0.5 m torso; Sub-6 stays >15.5 dB Es/N0."),
        ("Assumption:", "Equal 22 dB LoS Es/N0 assumes mmWave beamforming gain offsets +18.1 dB FSPL and +10 dB noise floor."),
    ], font_size=10.5, space_after=4)

    # Embedded Diffraction Validation Plot
    s4.shapes.add_picture(os.path.join(PLOT_DIR, "diffraction_validation.png"), Inches(7.0), Inches(1.50), width=Inches(5.75))
    cap = s4.shapes.add_textbox(Inches(7.0), Inches(4.55), Inches(5.75), Inches(2.2))
    ctf = cap.text_frame
    ctf.word_wrap = True
    cp = ctf.paragraphs[0]
    cp.text = "Diffraction Verification (validate_physics_to_bits.py)"
    cp.font.name = FONT_MAIN
    cp.font.size = Pt(12)
    cp.font.bold = True
    cp.font.color.rgb = NAVY
    add_bullets(s4, 7.0, 4.92, 5.75, 1.9, [
        ("Exact Fresnel (ν=0):", "6.0206 dB (exact analytical check)."),
        ("Shadow match (ν ∈ [0, 4]):", "Max gap 0.19 dB vs. exact Fresnel."),
        ("4-edge asymptotic limits:", "W,H → 1000m gives 6.0095 dB; λ → 300m gives 0.0071 dB."),
    ], font_size=10.5, space_after=5)

    # =========================================================================
    # SLIDE 5: ALGEBRAIC CODING (CRC-16 & GF(2^8) RS)
    # =========================================================================
    s5 = prs.slides.add_slide(blank)
    add_header(s5, "Algebraic Error Detection & Correction (coding.py)", "Zero black-box FEC libraries — every CRC remainder, GF(2⁸) syndrome, and byte repair is inspectable", 5)

    add_card(s5, 0.6, 1.48, 5.85, 5.35, "CRC-16/XMODEM & 18-Byte Chunking", accent=CYAN)
    add_bullets(s5, 0.85, 2.02, 5.35, 4.6, [
        ("Why 18-byte chunks?", "RS(t=2) succeeds with binomial probability Σ(k=0..2) C(N,k) p_B^k (1−p_B)^(N−k). Keeping N=24 (18B payload) maintains ~90% grazing survival vs. ~13% for 100B blocks."),
        ("Exact CRC configuration:", "CRC-16/XMODEM: G(x) = x¹⁶ + x¹² + x⁵ + 1 (0x1021), init=0x0000, no reflection, no final XOR."),
        ("Receiver zero-check:", "Verifies (M(x)·x¹⁶ + CRC(x)) mod G(x) == 0x0000 via bit-by-bit polynomial long division."),
        ("Exhaustive burst test:", "Verified across every starting bit position for all burst lengths 1..16 bits."),
        ("Parity-only nuance:", "CRC sits inside systematic RS and covers message bytes only; parity-only flips show P2 PASS while P3 still fixes parity."),
    ], font_size=11.5, space_after=8)

    add_card(s5, 6.85, 1.48, 5.88, 5.35, "Systematic Shortened GF(2⁸) RS(24, 20)", accent=TEAL)
    add_bullets(s5, 7.1, 2.02, 5.4, 4.6, [
        ("Finite field GF(2⁸):", "Primitive polynomial x⁸ + x⁴ + x³ + x² + 1 (0x11D), α = 2; systematic encoding leaves [payload || CRC] intact + 4 parity bytes (t = 2)."),
        ("Decoder pipeline:", "1) Syndromes S_j = r(α^j)  →  2) Berlekamp-Massey Λ(x)  →  3) Chien search  →  4) Forney magnitudes  →  5) Re-verify S_j == 0."),
        ("Shortened-block guard:", "Chien search requires all roots inside [0, N−1]. Miscorrection drops from ~1/t! (50%) to ~(1/2!)(24/256)² = 0.44%."),
        ("Empirical check (10,000 5-byte errors):", "37/10,000 RS miscorrections (0.37%), and 0/10,000 escaped the post-decode CRC-16 gate."),
        ("Analytical escape bound:", "Conditional CRC escape ≈ 2⁻¹⁶ (~1.5×10⁻⁵) → overall undetected rate ≈ 5.6×10⁻⁸ per >t-error block."),
    ], font_size=11.5, space_after=8)

    # =========================================================================
    # SLIDE 6: 3-PROGRAM INTERACTIVE OPEN5GS PIPELINE
    # =========================================================================
    s6 = prs.slides.add_slide(blank)
    add_header(s6, "3-Program Interactive Open5GS Pipeline", "Real stop-and-wait ARQ over isolated UE namespaces (ue1 → Open5GS UPF GTP-U 2152 → ue2)", 6)

    progs = [
        ("Program 1: UE 1 TX & Channel", "prog1_tx_channel.py  (netns ue1)", CYAN, [
            ("Interactive input:", "Type any message (auto-chunked ≤18B), move blocker (clear / edge / center / x=<m>), or switch all 6 scenarios live."),
            ("mmWave-first TX:", "Applies 28 GHz diffraction + 16-QAM + AWGN and sends ONLY on :5001 first."),
            ("Clean RTT timer:", "Channel sim runs before t0 = perf_counter() so RTT measures pure network + P2/P3 time."),
            ("Bounded ARQ:", "1 retry on ACK timeout; up to 2 Sub-6 retransmissions (:5002) only if NACK arrives."),
        ]),
        ("Program 2: CRC-16 Detector", "prog2_crc_detector.py  (netns ue2)", AMBER, [
            ("Observability tap:", "Binds ue2:uesimtun0 (:5001, :5002), logs raw channel damage, and forwards untouched packets to P3."),
            ("No cheat flags:", "Checks (M·x¹⁶ + CRC) mod G == 0x0000; header x and Es/N0 are display-only telemetry."),
            ("Honest detection:", "Never sees original text, so it detects corruption mathematically without string diffing."),
            ("Strict validation:", "Rejects truncated, trailing-byte, or malformed UDP frames via unpack_frame()."),
        ]),
        ("Program 3: RS & Sub-6 ARQ", "prog3_rs_resilience.py  (netns ue2)", TEAL, [
            ("Algebraic repair:", "Runs GF(2⁸) RS + post-decode CRC-16; prints exact pos=[...] and raw -> repaired text."),
            ("Bounded replay cache:", "OrderedDict (cap 4096) suppresses duplicate deliveries and re-ACKs if feedback was lost."),
            ("Reactive NACK:", "When >2 bytes fail, drops mmWave packet and sends NACK (:5004) over UPF back to UE 1."),
            ("Sub-6 rescue:", "Decodes 3.5 GHz retransmission, verifies CRC-16, and sends Sub-6 ACK."),
        ]),
    ]
    for i, (title, sub, col, items) in enumerate(progs):
        px = 0.6 + i * 4.15
        add_card(s6, px, 1.48, 3.85, 5.35, title, accent=col)
        st = s6.shapes.add_textbox(Inches(px + 0.22), Inches(1.90), Inches(3.5), Inches(0.3))
        sp = st.text_frame.paragraphs[0]
        sp.text = sub
        sp.font.name = FONT_MONO
        sp.font.size = Pt(9.5)
        sp.font.color.rgb = MUTED
        add_bullets(s6, px + 0.20, 2.28, 3.50, 4.4, items, font_size=10.8, space_after=7)
        if i < 2:
            arr = s6.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(px + 3.89), Inches(3.95), Inches(0.22), Inches(0.32))
            arr.fill.solid()
            arr.fill.fore_color.rgb = MUTED
            arr.line.fill.background()

    # =========================================================================
    # SLIDE 7: LIVE DEMO TRACE
    # =========================================================================
    s7 = prs.slides.add_slide(blank)
    add_header(s7, "Live Demo Trace: Repair vs. Sub-6 Rescue", "Verified end-to-end execution showing LoS, grazing RS repair, center NACK rescue, and truck-blockage limit", 7)

    # Terminal window card
    term = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(1.45), Inches(12.13), Inches(4.15))
    term.adjustments[0] = 0.02
    term.fill.solid()
    term.fill.fore_color.rgb = TERM_BG
    term.line.color.rgb = RGBColor(0x33, 0x41, 0x55)

    ttb = s7.shapes.add_textbox(Inches(0.85), Inches(1.62), Inches(11.65), Inches(3.85))
    ttf = ttb.text_frame
    ttf.word_wrap = True
    lines = [
        ("# 1. CLEAR LoS (x = -0.75 m, urban_high, 28 GHz Es/N0 = +21.85 dB)", MUTED),
        ('P2: seq=0000 [28 GHz]  R(x)=0x0000 [✓ PASS]       | "HELLO 5G SURATHKAL"', TERM_GREEN),
        ('P3: seq=0000 [MMW CLEAN]       | peak 872.8 Mbps  | S=[0, 0, 0, 0] | "HELLO 5G SURATHKAL"', TERM_GREEN),
        ("", TERM_TEXT),
        ("# 2. GRAZING EDGE (x = -0.22 m, 28 GHz L = 7.39 dB, Es/N0 = +14.61 dB) — REPAIRED ON mmWave", MUTED),
        ('P2: seq=0001 [28 GHz]  R(x)=0x390D [✗ CORRUPTED]  | "HEDLO PROFESSOR"', TERM_RED),
        ('P3: seq=0001 [MMW RS FIXED 1B] | peak 872.8 Mbps  | pos=[2] | "HEDLO PROFESSOR" -> "HELLO PROFESSOR"', TERM_CYAN),
        ("", TERM_TEXT),
        ("# 3. DEAD CENTER (x = 0.00 m, 28 GHz L = 14.09 dB vs 3.5 GHz L = 6.46 dB) — NACK -> SUB-6 RESCUE", MUTED),
        ('P3: seq=0003 [MMW DROPPED->NACK] | "HE.\\E ..KM RD.6" | uncorrectable -> requesting Sub-6', TERM_RED),
        ('P1: [NACK 28 GHz -> SUB-6 ATTEMPT 1/2] Retransmitting on 3.5 GHz (Es/N0 = +15.54 dB)...', TERM_YELLOW),
        ('P3: seq=0003 [SUB-6 RESCUED]     | peak  91.9 Mbps | pos=[3]: "HEL.O FROM SUB6" -> "HELLO FROM SUB6"', TERM_YELLOW),
    ]
    for idx, (txt, col) in enumerate(lines):
        p = ttf.paragraphs[0] if idx == 0 else ttf.add_paragraph()
        p.space_after = Pt(2)
        r = p.add_run()
        r.text = txt
        r.font.name = FONT_MONO
        r.font.size = Pt(10.5)
        r.font.color.rgb = col

    # Bottom contrast card
    add_card(s7, 0.6, 5.80, 12.13, 1.15, "Honest Edge Case Verified Live: rural_low (W = 2.4 m Highway Truck at Center)", accent=AMBER, fill_color=CARD_ALT)
    tb7 = s7.shapes.add_textbox(Inches(0.85), Inches(6.24), Inches(11.65), Inches(0.65))
    tf7 = tb7.text_frame
    tf7.word_wrap = True
    p7 = tf7.paragraphs[0]
    p7.text = (
        "Behind a 2.4 m truck, 28 GHz loses 21.20 dB (Es/N0 = +0.80 dB) AND 3.5 GHz loses 12.66 dB (Es/N0 = +9.34 dB, Eb/N0 = +3.32 dB → ~7% BER). "
        "Fixed 16-QAM + RS(t=2) fails on BOTH bands — proving Sub-6 isn't rigged and showing exactly where real 5G requires AMC (QPSK + low-rate LDPC)."
    )
    p7.font.name = FONT_MAIN
    p7.font.size = Pt(11)
    p7.font.color.rgb = SLATE

    # =========================================================================
    # SLIDE 8: BASEBAND BER VALIDATION
    # =========================================================================
    s8 = prs.slides.add_slide(blank)
    add_header(s8, "Baseband Validation: Empirical BER vs. Q-Function", "Confirming Gray constellation mapping, unit-energy normalization, and √(N₀/2) noise scaling", 8)

    s8.shapes.add_picture(os.path.join(PLOT_DIR, "ber_validation.png"), Inches(0.6), Inches(1.48), width=Inches(7.75))

    add_card(s8, 8.6, 1.48, 4.13, 5.35, "Validation Methodology & Results", accent=CYAN)
    add_bullets(s8, 8.82, 2.02, 3.7, 4.6, [
        ("Stopping criterion:", "Target 100 bit errors per Eb/N0 point, capped at 10⁷ bits (high-SNR points: QPSK 10 dB = 33/10⁷, 16-QAM 14 dB = 26/10⁷)."),
        ("QPSK (0–10 dB):", "Matches exact P_b = Q(√(2 Eb/N0)) down to 3.3×10⁻⁶."),
        ("16-QAM (0–14 dB):", "Matches Gray nearest-neighbor P_b ≈ (3/4)Q(√(4/5 Eb/N0)) down to 2.6×10⁻⁶."),
        ("Why it matters:", "Proves our baseband modulator, Es = 1 scaling, AWGN variance N₀/2 per axis, and ML demapper are mathematically exact."),
    ], font_size=11.2, space_after=9)

    # =========================================================================
    # SLIDE 9: MULTI-SEED CONTINUOUS CROSSING RESULTS
    # =========================================================================
    s9 = prs.slides.add_slide(blank)
    add_header(s9, "Multi-Seed Continuous Crossing Results (41,000 Frames)", "5 independent seeds × 200 continuous 41-step trajectories (urban_high, ideal feedback)", 9)

    s9.shapes.add_picture(os.path.join(PLOT_DIR, "crossing_resilience.png"), Inches(0.55), Inches(1.36), height=Inches(5.60))

    headers9 = ["Scheme", "Controlled FER", "95% Wilson CI"]
    rows9 = [
        ["Raw 28 GHz", "29.47%", "[29.03%, 29.91%]"],
        ["28 GHz + RS(24,20)", "26.40%", "[25.97%, 26.83%]"],
        ["Open-Loop (2-fr drop)", "5.13%", "[4.92%, 5.35%]"],
        ["ARQ (1 Sub-6 retx)", "0.19%", "[0.15%, 0.24%]"],
    ]
    add_table(s9, 6.45, 1.48, 6.28, 2.35, headers9, rows9, col_widths=[2.40, 1.55, 2.33], font_size=10.5)

    add_card(s9, 6.45, 4.05, 6.28, 2.85, "Per-Seed Stability & Rate Interpretation", accent=TEAL)
    add_bullets(s9, 6.68, 4.55, 5.85, 2.25, [
        ("ARQ per-seed FER (seeds 42–46):", "0.17%, 0.17%, 0.18%, 0.27%, 0.17% (79 / 41,000 total failures)."),
        ("Continuous open-loop baseline:", "Carries switch state continuously across all 41 positions (5.09%–5.22% per seed)."),
        ("Delivering-link rate (Panel 3):", "Modelled from TS 38.306 structure (872.8 → 91.9 Mbps); ignores ARQ retx/idle airtime."),
        ("Controlled simulation scope:", "Results characterize controlled channel recovery under ideal feedback, not a commercial 5G SLA."),
    ], font_size=10.8, space_after=6)

    # =========================================================================
    # SLIDE 10: VERIFICATION, BOUNDARIES & TAKEAWAYS
    # =========================================================================
    s10 = prs.slides.add_slide(blank)
    add_header(s10, "Engineering Rigor, Scope Boundaries & Takeaways", "Defensive validation completed and explicit assumptions documented for viva defense", 10)

    add_card(s10, 0.6, 1.48, 5.85, 4.15, "Defensive Engineering & Verification Passed", accent=TEAL)
    add_bullets(s10, 0.85, 2.02, 5.35, 3.4, [
        ("Adversarial packet tests:", "0/1/2/6-byte truncated frames, trailing garbage, invalid link_id/flags/feedback codes, nsym=0/1, and empty RS/CRC buffers all strictly rejected."),
        ("ARQ robustness:", "Stop-and-wait framing, bounded OrderedDict replay window (4096) for duplicate suppression, and validated CLI bounds."),
        ("Independent coding checks:", "Exhaustive ≤16-bit CRC bursts, 400/400 random RS repairs, 0.37% shortened-RS miscorrection (0/10,000 CRC escapes)."),
        ("Open5GS GTP-U verified:", "Live UE1 ↔ UE2 traffic confirmed over uesimtun0 and Open5GS UPF with real perf_counter RTT."),
    ], font_size=11.2, space_after=8)

    add_card(s10, 6.85, 1.48, 5.88, 4.15, "Explicit Scope Boundaries (Honest Viva Framing)", accent=AMBER)
    add_bullets(s10, 7.1, 2.02, 5.4, 3.4, [
        ("Real 5G NR vs. demo:", "Real 5G uses LDPC + AMC (QPSK/low-rate coding) and RRC RSRP events (A2/A3/B1); blockage resilience is one motivation for NR-DC alongside NSA & aggregation."),
        ("Payload-only channel:", "Transport headers and ACK/NACK feedback are uncorrupted control metadata outside the AWGN channel."),
        ("Geometry & fading:", "Fixed H=1.7 m, d₁=1.5 m, d₂=10.0 m; small-scale fading omitted intentionally to isolate deterministic diffraction loss."),
        ("Rate vs. latency:", "872.8 / 91.9 Mbps are modelled PHY delivering-link rates; real network latency is measured via perf_counter RTT."),
    ], font_size=11.2, space_after=8)

    # Bottom takeaway banner
    banner = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(5.85), Inches(12.13), Inches(1.05))
    banner.adjustments[0] = 0.08
    banner.fill.solid()
    banner.fill.fore_color.rgb = BG_DARK
    banner.line.fill.background()
    btb = s10.shapes.add_textbox(Inches(0.9), Inches(6.02), Inches(11.5), Inches(0.75))
    btf = btb.text_frame
    btf.word_wrap = True
    bp = btf.paragraphs[0]
    bp.alignment = PP_ALIGN.CENTER
    bp.text = (
        "Core Takeaway:  Small grazing damage → repaired on 28 GHz by GF(2⁸) Reed-Solomon (872.8 Mbps peak).   "
        "Deep center blockage → rescued by 3.5 GHz Sub-6 ARQ fallback (91.9 Mbps, cutting FER from 29.47% to 0.19%)."
    )
    bp.font.name = FONT_MAIN
    bp.font.size = Pt(13)
    bp.font.bold = True
    bp.font.color.rgb = LIGHT_CYAN

    prs.save(OUT_PPTX)
    print(f"Saved presentation: {OUT_PPTX}")


if __name__ == "__main__":
    build()

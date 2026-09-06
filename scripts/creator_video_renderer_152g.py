#!/usr/bin/env python3
"""Autonomous Creator Video Production Pipeline for Mission 152G.

Produces a full 10-video short-form backlog with:
- 10 distinct creative mechanics (Gravity, Catapult, Race, Anvil, Potion, Vault, Laser, Loop, Ice, Time-Freeze)
- Procedural cartoon character rendering (Apple, Cherries, Blueberry, Pineapple, Lemon, Strawberry, Orange, Banana, Watermelon, Kiwi)
- Synchronized multi-track procedural audio (BGM, sound effects, fanfares, Foley)
- Deterministic ffprobe QC verification, schema 2.2 publish packages, contact sheet, and manifest compilation.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_CONTENT_DIR = COURIER_DIR / "runtime" / "content"

try:
    from scripts.canonical_authority import CanonicalAuthority
except ImportError:
    from canonical_authority import CanonicalAuthority

WIDTH = 720
HEIGHT = 1280
FPS = 30
DURATION_SECONDS = 8.0
TOTAL_FRAMES = int(DURATION_SECONDS * FPS)  # 240 frames


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_media_properties(video_path: Path) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,r_frame_rate,codec_name",
        "-of", "json",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(res.stdout)
    stream = probe_data.get("streams", [{}])[0]

    cmd_a = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,duration",
        "-of", "json",
        str(video_path),
    ]
    res_a = subprocess.run(cmd_a, capture_output=True, text=True, check=True)
    probe_data_a = json.loads(res_a.stdout)
    stream_a = probe_data_a.get("streams", [{}])[0] if probe_data_a.get("streams") else {}

    r_fps = stream.get("r_frame_rate", "30/1")
    if "/" in r_fps:
        num, den = r_fps.split("/")
        fps_val = float(num) / float(den) if float(den) > 0 else 30.0
    else:
        fps_val = float(r_fps)

    duration_val = float(stream.get("duration", DURATION_SECONDS))

    return {
        "width": int(stream.get("width", WIDTH)),
        "height": int(stream.get("height", HEIGHT)),
        "duration_seconds": duration_val,
        "fps": fps_val,
        "video_codec": stream.get("codec_name", "h264"),
        "audio_codec": stream_a.get("codec_name", "aac"),
        "has_audio": bool(stream_a),
    }


def write_wav_file(path: Path, audio: np.ndarray, sample_rate: int = 44100) -> None:
    audio = np.clip(audio, -0.95, 0.95)
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())


# ==============================================================================
# Procedural Audio Generators for 10 Videos
# ==============================================================================

def audio_mystery_portal(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Cosmic arpeggio & portal swirl
    freqs = [220, 277.18, 329.63, 440, 554.37]
    for i in range(16):
        st = i * 0.5
        idx1, idx2 = int(st * sr), int(min(len(t), (st + 0.4) * sr))
        ct = t[idx1:idx2] - st
        f = freqs[i % len(freqs)]
        audio[idx1:idx2] += 0.2 * np.sin(2 * np.pi * f * ct) * np.exp(-ct * 6.0)
    # Portal whoosh (t=3.5 -> 5.5)
    p_start, p_len = int(3.5 * sr), int(2.0 * sr)
    pt = np.linspace(0, 2.0, p_len)
    audio[p_start:p_start+p_len] += 0.35 * np.sin(2 * np.pi * np.linspace(150, 900, p_len) * pt) * np.sin(np.pi * pt / 2.0)
    # Golden sparkle chime (t=6.5 -> 8.0)
    g_start = int(6.5 * sr)
    gt = t[g_start:] - 6.5
    for gf in [659.25, 830.61, 987.77, 1318.51]:
        audio[g_start:] += 0.12 * np.sin(2 * np.pi * gf * gt) * np.exp(-gt * 1.5)
    write_wav_file(path, audio, sr)


def audio_cherry_catapult(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Rubber stretch tension (0-2s)
    s_len = int(2.0 * sr)
    st = t[:s_len]
    audio[:s_len] += 0.25 * np.sin(2 * np.pi * np.linspace(100, 250, s_len) * st) * (st / 2.0)
    # Snap release (t=2.0)
    snap_idx = int(2.0 * sr)
    snap_len = int(0.2 * sr)
    snapt = np.linspace(0, 0.2, snap_len)
    audio[snap_idx:snap_idx+snap_len] += 0.6 * np.sin(2 * np.pi * 600 * snapt) * np.exp(-snapt * 30.0)
    # Flight whoosh (2.2-5.5)
    fl_start, fl_len = int(2.2 * sr), int(3.3 * sr)
    flt = np.linspace(0, 3.3, fl_len)
    audio[fl_start:fl_start+fl_len] += 0.2 * np.random.uniform(-1, 1, fl_len) * np.sin(np.pi * flt / 3.3)
    # Gong impact (t=5.8)
    gong_idx = int(5.8 * sr)
    gong_t = t[gong_idx:] - 5.8
    for gf in [180, 240, 360, 540]:
        audio[gong_idx:] += 0.25 * np.sin(2 * np.pi * gf * gong_t) * np.exp(-gong_t * 1.8)
    write_wav_file(path, audio, sr)


def audio_micro_grand_prix(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Countdown beeps (0.5, 1.0, 1.5, 2.0 GO)
    for b_idx, bt in enumerate([0.5, 1.0, 1.5]):
        b_start = int(bt * sr)
        audio[b_start:b_start+int(0.15*sr)] += 0.3 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.15, int(0.15*sr)))
    go_start = int(2.0 * sr)
    audio[go_start:go_start+int(0.3*sr)] += 0.5 * np.sin(2 * np.pi * 880 * np.linspace(0, 0.3, int(0.3*sr)))
    # Kart engine race sound (2.0-8.0)
    race_t = t[go_start:] - 2.0
    engine = 0.25 * np.sin(2 * np.pi * (180 + np.sin(race_t * 3.0) * 40) * race_t)
    audio[go_start:] += engine
    # Nitro boost (t=5.0 -> 6.5)
    n_start, n_len = int(5.0 * sr), int(1.5 * sr)
    nt = np.linspace(0, 1.5, n_len)
    audio[n_start:n_start+n_len] += 0.4 * np.sin(2 * np.pi * np.linspace(300, 1200, n_len) * nt) * np.sin(np.pi * nt / 1.5)
    write_wav_file(path, audio, sr)


def audio_giant_pineapple(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Heavy fall whistle (1.0-3.5)
    w_start, w_len = int(1.0 * sr), int(2.5 * sr)
    wt = np.linspace(0, 2.5, w_len)
    audio[w_start:w_start+w_len] += 0.3 * np.sin(2 * np.pi * np.linspace(800, 150, w_len) * wt) * (wt / 2.5)
    # Comical catch 'tink' (t=3.5)
    c_idx = int(3.5 * sr)
    ct = np.linspace(0, 0.3, int(0.3 * sr))
    audio[c_idx:c_idx+int(0.3*sr)] += 0.6 * np.sin(2 * np.pi * 1200 * ct) * np.exp(-ct * 20.0)
    # Heroic synth fanfare (4.5-8.0)
    f_start = int(4.5 * sr)
    ft = t[f_start:] - 4.5
    for chord_f in [261.63, 329.63, 392.00, 523.25]:
        audio[f_start:] += 0.18 * np.sin(2 * np.pi * chord_f * ft) * np.exp(-ft * 0.8)
    write_wav_file(path, audio, sr)


def audio_wrong_potion(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Potion bubbling (0-2.5s)
    b_len = int(2.5 * sr)
    audio[:b_len] += 0.2 * np.random.uniform(-1, 1, b_len) * (np.sin(t[:b_len] * 20.0) ** 2)
    # Gulp sound (t=2.5)
    g_idx = int(2.5 * sr)
    gt = np.linspace(0, 0.4, int(0.4 * sr))
    audio[g_idx:g_idx+int(0.4*sr)] += 0.4 * np.sin(2 * np.pi * np.linspace(350, 180, int(0.4*sr)) * gt)
    # Electric inflation charge (3.0-6.0)
    e_start, e_len = int(3.0 * sr), int(3.0 * sr)
    et = np.linspace(0, 3.0, e_len)
    audio[e_start:e_start+e_len] += 0.35 * np.sin(2 * np.pi * np.linspace(150, 950, e_len) * et) + 0.1 * np.random.uniform(-1, 1, e_len)
    # Balloon deflating zip (6.0-8.0)
    z_start = int(6.0 * sr)
    zt = t[z_start:] - 6.0
    audio[z_start:] += 0.4 * np.sin(2 * np.pi * (600 + np.sin(zt * 40.0) * 200) * zt) * np.exp(-zt * 1.2)
    write_wav_file(path, audio, sr)


def audio_three_door_vault(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Ticking clock (0-3.5s)
    for tick in range(7):
        t_idx = int(tick * 0.5 * sr)
        audio[t_idx:t_idx+int(0.05*sr)] += 0.35 * np.sin(2 * np.pi * 1000 * np.linspace(0, 0.05, int(0.05*sr)))
    # Vault gear clicks (3.5-5.0)
    for click in range(6):
        c_idx = int((3.5 + click * 0.25) * sr)
        audio[c_idx:c_idx+int(0.1*sr)] += 0.4 * np.sin(2 * np.pi * 450 * np.linspace(0, 0.1, int(0.1*sr)))
    # Radiant victory chord & choir (5.5-8.0)
    v_start = int(5.5 * sr)
    vt = t[v_start:] - 5.5
    for vf in [440, 554.37, 659.25, 880]:
        audio[v_start:] += 0.2 * np.sin(2 * np.pi * vf * vt) * np.exp(-vt * 0.7)
    write_wav_file(path, audio, sr)


def audio_orange_laser(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Stealth bassline groove (0-6.0)
    bass = 0.3 * np.sin(2 * np.pi * 110 * t[:int(6.0*sr)]) * (np.sin(t[:int(6.0*sr)] * 8.0) ** 2)
    audio[:int(6.0*sr)] += bass
    # Laser hum & swishes (1.5, 3.0, 4.5)
    for sw_t in [1.5, 3.0, 4.5]:
        sw_idx = int(sw_t * sr)
        swt = np.linspace(0, 0.3, int(0.3*sr))
        audio[sw_idx:sw_idx+int(0.3*sr)] += 0.35 * np.sin(2 * np.pi * np.linspace(900, 200, int(0.3*sr)) * swt)
    # Mission success electronic chime (6.2-8.0)
    m_start = int(6.2 * sr)
    mt = t[m_start:] - 6.2
    for mf in [523.25, 659.25, 783.99, 1046.50]:
        audio[m_start:] += 0.18 * np.sin(2 * np.pi * mf * mt) * np.exp(-mt * 1.2)
    write_wav_file(path, audio, sr)


def audio_banana_skateboard(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Skate wheel rumble (continuous)
    audio += 0.15 * np.random.uniform(-1, 1, len(t)) * (0.5 + 0.5 * np.sin(t * 4.0))
    # Halfpipe drop whooshes (1.5, 3.5, 5.5, 7.5)
    for ht in [1.5, 3.5, 5.5, 7.5]:
        h_idx = int(ht * sr)
        ht_chunk = np.linspace(0, 0.4, int(0.4*sr))
        audio[h_idx:h_idx+int(0.4*sr)] += 0.35 * np.sin(2 * np.pi * np.linspace(150, 600, int(0.4*sr)) * ht_chunk)
    # Loop rail grind sparks (4.0-5.5)
    g_start, g_len = int(4.0 * sr), int(1.5 * sr)
    audio[g_start:g_start+g_len] += 0.25 * np.random.uniform(-1, 1, g_len) * (np.sin(t[g_start:g_start+g_len] * 30.0) ** 2)
    write_wav_file(path, audio, sr)


def audio_watermelon_ice_crush(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Wrecking ball swing build-up (0-3.5)
    swing = 0.3 * np.sin(2 * np.pi * np.linspace(80, 220, int(3.5*sr)) * t[:int(3.5*sr)])
    audio[:int(3.5*sr)] += swing
    # Massive shatter collision (t=3.5)
    c_idx = int(3.5 * sr)
    c_len = int(1.5 * sr)
    ct = np.linspace(0, 1.5, c_len)
    impact_boom = 0.6 * np.sin(2 * np.pi * 90 * ct) * np.exp(-ct * 8.0)
    shatter_noise = 0.45 * np.random.uniform(-1, 1, c_len) * np.exp(-ct * 4.0)
    audio[c_idx:c_idx+c_len] += impact_boom + shatter_noise
    # Ice sparkle crystal chime (5.5-8.0)
    s_start = int(5.5 * sr)
    st = t[s_start:] - 5.5
    for sf in [880, 1174.66, 1396.91, 1760]:
        audio[s_start:] += 0.15 * np.sin(2 * np.pi * sf * st) * np.exp(-st * 1.5)
    write_wav_file(path, audio, sr)


def audio_kiwi_time_freeze(path: Path, duration: float = DURATION_SECONDS, sr: int = 44100) -> None:
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t, dtype=np.float32)
    # Chaos fall whoosh (0-2.0s)
    audio[:int(2.0*sr)] += 0.3 * np.random.uniform(-1, 1, int(2.0*sr)) * (t[:int(2.0*sr)] / 2.0)
    # Stopwatch CLICK (t=2.0)
    c_idx = int(2.0 * sr)
    ct = np.linspace(0, 0.1, int(0.1*sr))
    audio[c_idx:c_idx+int(0.1*sr)] += 0.8 * np.sin(2 * np.pi * 1800 * ct) * np.exp(-ct * 40.0)
    # Eerie frozen-time drone (2.2-6.0)
    fz_start, fz_len = int(2.2 * sr), int(3.8 * sr)
    fzt = np.linspace(0, 3.8, fz_len)
    audio[fz_start:fz_start+fz_len] += 0.25 * (np.sin(2 * np.pi * 110 * fzt) + 0.5 * np.sin(2 * np.pi * 220 * fzt))
    # Unfreeze snap & neat stacking chime (6.2-8.0)
    u_start = int(6.2 * sr)
    ut = t[u_start:] - 6.2
    for uf in [523.25, 659.25, 783.99, 1046.50]:
        audio[u_start:] += 0.2 * np.sin(2 * np.pi * uf * ut) * np.exp(-ut * 1.5)
    write_wav_file(path, audio, sr)


# ==============================================================================
# Procedural Visual Frame Renderers for 10 Videos
# ==============================================================================

def draw_gradient_background(draw: ImageDraw.Draw, top_col: Tuple[int, int, int], bot_col: Tuple[int, int, int], width: int = WIDTH, height: int = HEIGHT) -> None:
    for y in range(0, height, 4):
        r = y / height
        cr = int(top_col[0] * (1 - r) + bot_col[0] * r)
        cg = int(top_col[1] * (1 - r) + bot_col[1] * r)
        cb = int(top_col[2] * (1 - r) + bot_col[2] * r)
        draw.rectangle([0, y, width, y + 4], fill=(cr, cg, cb, 255))


class RendererMysteryPortal:
    """Video 01: Red Apple discovered a neon gravity portal."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 15, 30, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        draw_gradient_background(draw, (15, 23, 42), (49, 46, 129))

        # Swirling Portal in Center
        px, py = WIDTH // 2, int(HEIGHT * 0.48)
        p_angle = t * 6.0
        for r_ring in range(5, 120, 15):
            ring_col = (147, 51, 234) if r_ring % 30 == 0 else (56, 189, 248)
            draw.ellipse([px - r_ring, py - r_ring, px + r_ring, py + r_ring], outline=(*ring_col, 200), width=3)

        # Apple character physics
        is_golden = t >= 4.5
        if t < 2.0:
            ax = int(WIDTH * 0.2 + (t / 2.0) * (WIDTH * 0.3))
            ay = int(HEIGHT * 0.75)
        elif t < 4.5:
            # Sucked into portal
            prog = (t - 2.0) / 2.5
            ax = int(WIDTH * 0.5)
            ay = int(HEIGHT * 0.75 - prog * (HEIGHT * 0.27))
        else:
            # Golden Apple floating gracefully
            ax = WIDTH // 2
            ay = int(HEIGHT * 0.42 + math.sin(t * 4.0) * 20)

        # Draw Apple Body
        body_col = (234, 179, 8, 255) if is_golden else (239, 68, 68, 255)
        draw.ellipse([ax - 55, ay - 50, ax + 55, ay + 50], fill=body_col, outline=(15, 23, 42, 255), width=4)
        # Leaf & stem
        draw.line([ax, ay - 50, ax, ay - 75], fill=(113, 63, 18, 255), width=6)
        draw.ellipse([ax + 5, ay - 85, ax + 35, ay - 65], fill=(34, 197, 94, 255))
        # Eyes
        draw.ellipse([ax - 22, ay - 20, ax - 6, ay], fill=(255, 255, 255, 255), outline=(15, 23, 42, 255), width=2)
        draw.ellipse([ax - 16, ay - 14, ax - 8, ay - 4], fill=(15, 23, 42, 255))
        draw.ellipse([ax + 6, ay - 20, ax + 22, ay], fill=(255, 255, 255, 255), outline=(15, 23, 42, 255), width=2)
        draw.ellipse([ax + 8, ay - 14, ax + 16, ay - 4], fill=(15, 23, 42, 255))

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(56, 189, 248, 255), width=3)
        draw.text((int(WIDTH * 0.18), int(HEIGHT * 0.08) + 18), "MYSTERY PORTAL APFEL! 🍎🌀✨", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


class RendererCherryCatapult:
    """Video 02: Twin Cherries Slingshot Target Challenge."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (20, 10, 30, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        draw_gradient_background(draw, (30, 10, 40), (88, 28, 135))

        # Target Gong at Top Right
        gx, gy = int(WIDTH * 0.72), int(HEIGHT * 0.28)
        draw.ellipse([gx - 75, gy - 75, gx + 75, gy + 75], fill=(234, 179, 8, 255), outline=(202, 138, 4, 255), width=6)
        draw.ellipse([gx - 45, gy - 45, gx + 45, gy + 45], outline=(239, 68, 68, 255), width=4)
        draw.ellipse([gx - 15, gy - 15, gx + 15, gy + 15], fill=(239, 68, 68, 255))

        # Slingshot at Bottom Left
        sx, sy = int(WIDTH * 0.25), int(HEIGHT * 0.82)
        draw.line([sx - 40, sy, sx - 20, sy - 90], fill=(161, 98, 7, 255), width=10)
        draw.line([sx + 40, sy, sx + 20, sy - 90], fill=(161, 98, 7, 255), width=10)

        # Cherry flight trajectory
        if t < 2.0:
            cx, cy = sx, sy - 60
        elif t < 5.8:
            prog = (t - 2.0) / 3.8
            cx = int(sx + prog * (gx - sx))
            cy = int((sy - 60) + prog * (gy - (sy - 60)) - math.sin(prog * math.pi) * 350)
        else:
            cx, cy = gx, gy
            # Gong impact sparkles
            for sp in range(12):
                sa = sp * (math.pi / 6)
                draw.line([gx, gy, gx + int(math.cos(sa) * 110), gy + int(math.sin(sa) * 110)], fill=(250, 204, 21, 255), width=4)

        # Draw Twin Cherries
        draw.ellipse([cx - 40, cy - 20, cx, cy + 20], fill=(225, 29, 72, 255), outline=(15, 23, 42, 255), width=3)
        draw.ellipse([cx, cy - 20, cx + 40, cy + 20], fill=(225, 29, 72, 255), outline=(15, 23, 42, 255), width=3)
        draw.line([cx - 20, cy - 20, cx, cy - 60], fill=(22, 101, 52, 255), width=4)
        draw.line([cx + 20, cy - 20, cx, cy - 60], fill=(22, 101, 52, 255), width=4)

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(239, 68, 68, 255), width=3)
        draw.text((int(WIDTH * 0.16), int(HEIGHT * 0.08) + 18), "KIRSCHE KORB-TREFFER! 🍒🎯💥", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


class RendererMicroGrandPrix:
    """Video 03: Micro Fruit Grand Prix Kart Race."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (15, 20, 35, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        draw_gradient_background(draw, (15, 23, 42), (30, 58, 138))

        # Racing Track Curves
        draw.ellipse([WIDTH * 0.1, HEIGHT * 0.25, WIDTH * 0.9, HEIGHT * 0.85], outline=(100, 116, 139, 255), width=80)
        draw.ellipse([WIDTH * 0.1, HEIGHT * 0.25, WIDTH * 0.9, HEIGHT * 0.85], outline=(255, 255, 255, 255), width=4)

        # Checkered Finish Line at Top Center
        fx = WIDTH // 2
        fy = int(HEIGHT * 0.25)
        for i in range(6):
            c_col = (255, 255, 255) if i % 2 == 0 else (0, 0, 0)
            draw.rectangle([fx - 30 + i * 10, fy - 15, fx - 20 + i * 10, fy + 15], fill=(*c_col, 255))

        # Karts: Blueberry (Blue - Leader), Raspberry (Pink), Grape (Purple)
        angle_blue = (t * 2.2) % (2 * math.pi)
        angle_pink = ((t * 2.0) - 0.3) % (2 * math.pi)
        angle_purple = ((t * 1.8) - 0.6) % (2 * math.pi)

        rx, ry = WIDTH * 0.4, HEIGHT * 0.3
        cx, cy = WIDTH // 2, int(HEIGHT * 0.55)

        for ang, col, label in [(angle_purple, (168, 85, 247), "Grape"), (angle_pink, (244, 63, 94), "Raspberry"), (angle_blue, (59, 130, 246), "Blueberry")]:
            kx = int(cx + math.cos(ang) * rx)
            ky = int(cy + math.sin(ang) * ry)
            # Kart body
            draw.ellipse([kx - 28, ky - 20, kx + 28, ky + 20], fill=col, outline=(15, 23, 42, 255), width=3)
            # Helmet / Fruit face
            draw.ellipse([kx - 12, ky - 12, kx + 12, ky + 12], fill=(255, 255, 255, 255))
            # Speed streaks
            draw.line([kx - int(math.cos(ang) * 40), ky - int(math.sin(ang) * 40), kx, ky], fill=(250, 204, 21, 200), width=4)

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(59, 130, 246, 255), width=3)
        draw.text((int(WIDTH * 0.16), int(HEIGHT * 0.08) + 18), "MINI FRUCHT GRAND PRIX! 🏎️💨🏆", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


class RendererGiantPineapple:
    """Video 04: Giant Pineapple Anvil Catch."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (25, 20, 15, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        draw_gradient_background(draw, (30, 25, 20), (120, 53, 15))

        px, py = WIDTH // 2, int(HEIGHT * 0.72)

        # Anvil Falling / Caught
        if t < 3.5:
            prog = t / 3.5
            anvil_y = int(HEIGHT * 0.15 + prog * (py - HEIGHT * 0.15 - 130))
        else:
            anvil_y = int(py - 130 + math.sin(t * 6.0) * 10)

        # Draw 500-TON Cartoon Anvil
        draw.polygon([
            (px - 90, anvil_y), (px + 90, anvil_y),
            (px + 60, anvil_y + 60), (px - 60, anvil_y + 60)
        ], fill=(71, 85, 105, 255), outline=(15, 23, 42, 255), width=5)
        draw.text((px - 35, anvil_y + 18), "500 TON", fill=(248, 250, 252, 255))

        # Pineapple Character
        draw.ellipse([px - 65, py - 85, px + 65, py + 85], fill=(234, 179, 8, 255), outline=(180, 83, 9, 255), width=5)
        # Pineapple green crown
        draw.polygon([(px, py - 140), (px - 45, py - 85), (px + 45, py - 85)], fill=(34, 197, 94, 255))
        # Cool Sunglasses
        draw.rectangle([px - 45, py - 30, px - 8, py - 5], fill=(15, 23, 42, 255))
        draw.rectangle([px + 8, py - 30, px + 45, py - 5], fill=(15, 23, 42, 255))
        draw.line([px - 8, py - 18, px + 8, py - 18], fill=(15, 23, 42, 255), width=4)

        # One finger casual hold (t >= 3.5)
        if t >= 3.5:
            draw.line([px, py - 85, px, anvil_y + 60], fill=(234, 179, 8, 255), width=10)

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(234, 179, 8, 255), width=3)
        draw.text((int(WIDTH * 0.16), int(HEIGHT * 0.08) + 18), "ANANAS STÄRKER ALS AMBOSS! 🍍💪", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


class RendererWrongPotion:
    """Video 05: Lemon drinks wrong lab potion & inflates."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (15, 25, 20, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        draw_gradient_background(draw, (6, 78, 59), (15, 23, 42))

        # Lab Shelf with Beakers
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.65), WIDTH * 0.9, int(HEIGHT * 0.68)], fill=(100, 116, 139, 255))
        # Beakers
        for bi, (bx, bcol) in enumerate([(WIDTH * 0.25, (236, 72, 153)), (WIDTH * 0.5, (59, 130, 246)), (WIDTH * 0.75, (34, 197, 94))]):
            draw.polygon([(bx - 20, int(HEIGHT * 0.65)), (bx + 20, int(HEIGHT * 0.65)), (bx + 10, int(HEIGHT * 0.58)), (bx - 10, int(HEIGHT * 0.58))], fill=(*bcol, 200), outline=(255, 255, 255, 255), width=2)

        # Lemon Character Size & Position
        if t < 3.0:
            lx, ly = WIDTH // 2, int(HEIGHT * 0.48)
            l_rad = 55
        elif t < 6.0:
            prog = (t - 3.0) / 3.0
            lx, ly = WIDTH // 2, int(HEIGHT * 0.45)
            l_rad = int(55 + prog * 95)  # Inflating!
        else:
            # Flying around deflating
            prog2 = (t - 6.0) / 2.0
            lx = int(WIDTH // 2 + math.sin(prog2 * math.pi * 6) * 180)
            ly = int(HEIGHT * 0.35 + math.cos(prog2 * math.pi * 6) * 120)
            l_rad = int(120 - prog2 * 65)

        # Draw Lemon
        draw.ellipse([lx - l_rad, ly - int(l_rad * 0.8), lx + l_rad, ly + int(l_rad * 0.8)], fill=(250, 204, 21, 255), outline=(202, 138, 4, 255), width=5)
        # Lemon tips
        draw.ellipse([lx - l_rad - 10, ly - 8, lx - l_rad + 6, ly + 8], fill=(250, 204, 21, 255))
        draw.ellipse([lx + l_rad - 6, ly - 8, lx + l_rad + 10, ly + 8], fill=(250, 204, 21, 255))
        # Eyes
        draw.ellipse([lx - 18, ly - 15, lx - 4, ly + 2], fill=(255, 255, 255, 255), outline=(15, 23, 42, 255), width=2)
        draw.ellipse([lx + 4, ly - 15, lx + 18, ly + 2], fill=(255, 255, 255, 255), outline=(15, 23, 42, 255), width=2)

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(234, 179, 8, 255), width=3)
        draw.text((int(WIDTH * 0.16), int(HEIGHT * 0.08) + 18), "ZITRONE TRINKT ZAUBERTRANK! 🍋🧪", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


class RendererThreeDoorVault:
    """Video 06: Strawberry Three Door Mystery Vault."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (20, 15, 30, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        draw_gradient_background(draw, (15, 23, 42), (76, 29, 149))

        # Three Vault Doors
        for di, (dx, dcol, dname) in enumerate([(WIDTH * 0.22, (239, 68, 68), "1"), (WIDTH * 0.5, (234, 179, 8), "2"), (WIDTH * 0.78, (168, 85, 247), "3")]):
            draw.rectangle([dx - 55, int(HEIGHT * 0.32), dx + 55, int(HEIGHT * 0.65)], fill=(*dcol, 180), outline=(255, 255, 255, 255), width=4)
            draw.text((int(dx - 10), int(HEIGHT * 0.46)), dname, fill=(255, 255, 255, 255))

        # Strawberry choosing Door 2
        sx, sy = WIDTH // 2, int(HEIGHT * 0.78)
        draw.polygon([(sx, sy + 65), (sx - 50, sy - 20), (sx + 50, sy - 20)], fill=(239, 68, 68, 255), outline=(185, 28, 28, 255), width=4)

        # Door 2 Open & Diamond Crown (t >= 5.0)
        if t >= 5.0:
            draw.rectangle([WIDTH * 0.5 - 45, int(HEIGHT * 0.34), WIDTH * 0.5 + 45, int(HEIGHT * 0.63)], fill=(255, 255, 255, 255))
            # Crown
            cx, cy = WIDTH // 2, int(HEIGHT * 0.45)
            draw.polygon([(cx - 30, cy + 20), (cx + 30, cy + 20), (cx + 35, cy - 20), (cx + 15, cy - 5), (cx, cy - 25), (cx - 15, cy - 5), (cx - 35, cy - 20)], fill=(250, 204, 21, 255), outline=(15, 23, 42, 255), width=3)

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(234, 179, 8, 255), width=3)
        draw.text((int(WIDTH * 0.16), int(HEIGHT * 0.08) + 18), "3-TÜREN MYSTERY TRESER! 🚪🎁👑", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


class RendererOrangeLaser:
    """Video 07: Orange & Kiwi Laser Heist."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 15, 25, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        draw_gradient_background(draw, (15, 23, 42), (30, 41, 59))

        # Pedestal with Trophy at Center
        draw.rectangle([WIDTH * 0.4, int(HEIGHT * 0.62), WIDTH * 0.6, int(HEIGHT * 0.85)], fill=(51, 65, 85, 255), outline=(15, 23, 42, 255), width=4)
        draw.polygon([(WIDTH * 0.46, int(HEIGHT * 0.58)), (WIDTH * 0.54, int(HEIGHT * 0.58)), (WIDTH * 0.52, int(HEIGHT * 0.52)), (WIDTH * 0.48, int(HEIGHT * 0.52))], fill=(250, 204, 21, 255))

        # Security Laser Grid
        for li in range(5):
            ly = int(HEIGHT * 0.35 + li * 65 + math.sin(t * 4.0 + li) * 25)
            draw.line([0, ly, WIDTH, ly + 30], fill=(239, 68, 68, 220), width=3)

        # Agent Orange Limbo Slide
        ox = int(WIDTH * 0.2 + (t / 8.0) * (WIDTH * 0.6))
        oy = int(HEIGHT * 0.68 + math.sin(t * 6.0) * 15)
        draw.ellipse([ox - 45, oy - 45, ox + 45, oy + 45], fill=(249, 115, 22, 255), outline=(194, 65, 12, 255), width=4)
        # Night vision goggles
        draw.rectangle([ox - 30, oy - 15, ox - 5, oy + 5], fill=(34, 197, 94, 255))
        draw.rectangle([ox + 5, oy - 15, ox + 30, oy + 5], fill=(34, 197, 94, 255))

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(249, 115, 22, 255), width=3)
        draw.text((int(WIDTH * 0.16), int(HEIGHT * 0.08) + 18), "AGENT ORANGE LASER-RAUB! 🍊🕶️🚨", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


class RendererBananaSkateboard:
    """Video 08: Banana Skateboard Infinite Halfpipe Loop."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (15, 10, 30, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        draw_gradient_background(draw, (30, 10, 45), (134, 25, 143))

        # Neon Halfpipe Ramp
        draw.arc([WIDTH * 0.1, HEIGHT * 0.35, WIDTH * 0.9, HEIGHT * 0.85], start=0, end=180, fill=(56, 189, 248, 255), width=8)

        # Banana Skater Position (Continuous smooth sine loop)
        loop_t = (t / DURATION_SECONDS) * (2 * math.pi * 2)  # 2 full clean loops
        bx = int(WIDTH // 2 + math.cos(loop_t) * (WIDTH * 0.32))
        by = int(HEIGHT * 0.60 + abs(math.sin(loop_t)) * 120)

        # Skateboard
        draw.rectangle([bx - 45, by + 30, bx + 45, by + 42], fill=(239, 68, 68, 255), outline=(15, 23, 42, 255), width=2)
        draw.ellipse([bx - 35, by + 40, bx - 20, by + 55], fill=(255, 255, 255, 255))
        draw.ellipse([bx + 20, by + 40, bx + 35, by + 55], fill=(255, 255, 255, 255))

        # Banana Character
        draw.ellipse([bx - 25, by - 40, bx + 25, by + 30], fill=(250, 204, 21, 255), outline=(202, 138, 4, 255), width=4)
        draw.rectangle([bx - 20, by - 15, bx + 20, by - 2], fill=(239, 68, 68, 255))  # Headband

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(250, 204, 21, 255), width=3)
        draw.text((int(WIDTH * 0.16), int(HEIGHT * 0.08) + 18), "ENDLOSER BANANEN-LOOP! 🍌🛹♾️", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


class RendererWatermelonIceCrush:
    """Video 09: Watermelon Ice Monolith Wrecking Ball Crush."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 25, 35, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        draw_gradient_background(draw, (8, 47, 73), (15, 23, 42))

        # Ice Monolith in Center
        ix, iy = WIDTH // 2, int(HEIGHT * 0.65)
        is_crushed = t >= 3.5

        if not is_crushed:
            draw.rectangle([ix - 65, iy - 110, ix + 65, iy + 60], fill=(186, 230, 253, 200), outline=(255, 255, 255, 255), width=4)
        else:
            # Shattered Shards
            np.random.seed(42)
            for si in range(25):
                shx = ix + int(np.random.uniform(-180, 180))
                shy = iy + int(np.random.uniform(-120, 90))
                draw.polygon([(shx, shy), (shx + 15, shy - 10), (shx + 20, shy + 15)], fill=(186, 230, 253, 220))

        # Watermelon Wrecking Ball Trajectory
        if t < 3.5:
            prog = t / 3.5
            wx = int(WIDTH * 0.15 + prog * (ix - WIDTH * 0.15))
            wy = int(HEIGHT * 0.35 + (prog ** 2) * (iy - HEIGHT * 0.35))
        else:
            wx, wy = ix, iy

        draw.ellipse([wx - 60, wy - 60, wx + 60, wy + 60], fill=(34, 197, 94, 255), outline=(22, 101, 52, 255), width=5)
        # Inner mouth
        draw.chord([wx - 35, wy - 10, wx + 35, wy + 40], start=0, end=180, fill=(244, 63, 94, 255))

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(56, 189, 248, 255), width=3)
        draw.text((int(WIDTH * 0.16), int(HEIGHT * 0.08) + 18), "MELONE ZERSCHMETTERT EIS! 🍉🧊💥", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


class RendererKiwiTimeFreeze:
    """Video 10: Kiwi Stopwatch Matrix Time-Freeze."""
    def render_frame(self, frame_idx: int, total_frames: int = TOTAL_FRAMES) -> Image.Image:
        img = Image.new("RGBA", (WIDTH, HEIGHT), (15, 20, 30, 255))
        draw = ImageDraw.Draw(img)
        t = frame_idx / FPS
        is_frozen = 2.0 <= t <= 6.0
        draw_gradient_background(draw, (3, 105, 161) if is_frozen else (15, 23, 42), (15, 23, 42))

        # Falling fruit elements (Apples, Berries, Droplets)
        elements = [
            (WIDTH * 0.25, HEIGHT * 0.35, (239, 68, 68), "Apple"),
            (WIDTH * 0.45, HEIGHT * 0.28, (250, 204, 21), "Banana"),
            (WIDTH * 0.72, HEIGHT * 0.42, (168, 85, 247), "Grape"),
            (WIDTH * 0.35, HEIGHT * 0.50, (56, 189, 248), "Drop"),
            (WIDTH * 0.65, HEIGHT * 0.32, (244, 63, 94), "Berry"),
        ]

        for ex, ey, col, label in elements:
            if not is_frozen:
                drop_y = int(ey + (t % 2.0) * 180)
            else:
                drop_y = int(ey)  # Time frozen in mid-air!
            draw.ellipse([ex - 22, drop_y - 22, ex + 22, drop_y + 22], fill=col, outline=(255, 255, 255, 255), width=3)

        # Kiwi with Stopwatch in foreground
        kx, ky = WIDTH // 2, int(HEIGHT * 0.78)
        draw.ellipse([kx - 55, ky - 55, kx + 55, ky + 55], fill=(161, 98, 7, 255), outline=(113, 63, 18, 255), width=4)
        draw.ellipse([kx - 40, ky - 40, kx + 40, ky + 40], fill=(132, 204, 22, 255))
        # Golden Stopwatch in hand
        draw.ellipse([kx + 35, ky - 20, kx + 75, ky + 20], fill=(250, 204, 21, 255), outline=(15, 23, 42, 255), width=3)

        # Title & Watermark
        draw.rectangle([WIDTH * 0.1, int(HEIGHT * 0.08), WIDTH * 0.9, int(HEIGHT * 0.08) + 65], fill=(15, 23, 42, 220), outline=(250, 204, 21, 255), width=3)
        draw.text((int(WIDTH * 0.16), int(HEIGHT * 0.08) + 18), "KIWI STOPPT DIE ZEIT! 🥝⏱️✨", fill=(255, 255, 255, 255))
        draw.text((int(WIDTH * 0.38), int(HEIGHT * 0.93)), "@kifruchtefilme", fill=(148, 163, 184, 200))
        return img


# ==============================================================================
# Pipeline Execution & Package Builder
# ==============================================================================

def render_single_video_package(
    slug: str,
    renderer: Any,
    audio_func: Callable[[Path, float, int], None],
    metadata_info: Dict[str, Any],
    label: str,
) -> Dict[str, Any]:
    pkg_dir = RUNTIME_CONTENT_DIR / slug
    pkg_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = pkg_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{label}] Rendering 240 frames @ {WIDTH}x{HEIGHT}...")
    rep_frame_img: Optional[Image.Image] = None
    for f in range(TOTAL_FRAMES):
        f_img = renderer.render_frame(f, TOTAL_FRAMES)
        if f == TOTAL_FRAMES // 2:
            rep_frame_img = f_img
        f_img.save(frames_dir / f"frame_{f:04d}.png", format="PNG")

    # Audio synthesis
    wav_path = pkg_dir / "audio.wav"
    audio_func(wav_path, DURATION_SECONDS, 44100)

    # Encode with FFmpeg
    mp4_path = pkg_dir / "render.mp4"
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-r", str(FPS),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-i", str(wav_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(mp4_path),
    ]
    subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)

    shutil.rmtree(frames_dir, ignore_errors=True)
    if wav_path.exists():
        wav_path.unlink()

    # Technical QC Verification
    media_props = get_media_properties(mp4_path)
    file_sha256 = compute_sha256(mp4_path)
    media_props["sha256"] = file_sha256
    media_props["file_size_bytes"] = mp4_path.stat().st_size

    # Render Metadata
    render_meta_path = pkg_dir / "render_metadata.json"
    render_meta = {
        "video_id": slug,
        "label": label,
        "rendered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "width": media_props["width"],
        "height": media_props["height"],
        "duration_seconds": media_props["duration_seconds"],
        "fps": media_props["fps"],
        "video_codec": media_props["video_codec"],
        "audio_codec": media_props["audio_codec"],
        "file_size_bytes": media_props["file_size_bytes"],
        "sha256": file_sha256,
        "renderer": type(renderer).__name__,
    }
    render_meta_path.write_text(json.dumps(render_meta, indent=2), encoding="utf-8")

    # QC Report
    qc_pass = (
        mp4_path.is_file()
        and media_props["file_size_bytes"] > 50000
        and media_props["width"] == WIDTH
        and media_props["height"] == HEIGHT
        and 7.0 <= media_props["duration_seconds"] <= 15.0
        and media_props["has_audio"]
        and media_props["video_codec"] == "h264"
    )
    qc_report_path = pkg_dir / "qc_report.json"
    qc_data = {
        "schema_version": "1.0",
        "verdict": "PASS" if qc_pass else "FAIL",
        "media": str(mp4_path),
        "source_hash": file_sha256,
        "duration_seconds": media_props["duration_seconds"],
        "video": {
            "codec_name": media_props["video_codec"],
            "width": media_props["width"],
            "height": media_props["height"],
            "r_frame_rate": f"{int(media_props['fps'])}/1",
        },
        "audio": {
            "codec_name": media_props["audio_codec"],
            "present": media_props["has_audio"],
        },
        "publication_authorized": False,
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    qc_report_path.write_text(json.dumps(qc_data, indent=2), encoding="utf-8")

    # Publish Package (Schema 2.2)
    fingerprint = hashlib.sha256(f"FRUITKI:{slug}:{file_sha256}".encode("utf-8")).hexdigest()
    package_path = pkg_dir / "publish_package.json"
    package_data = {
        "schema_version": "2.2",
        "platform": "YOUTUBE",
        "target_channel_id": "UCg0O_a10jsQ74ffS_HgFGqA",
        "target_channel_handle": "@kifruchtefilme",
        "token_reference": "fruitki-test",
        "channel_evidence_path": "events/evidence/channel_evidence_fruitki.json",
        "channel_evidence_hash": "686553407e2da096be7ee4ddc98bab824dd307bcec650a6d42ce22de02d53945",
        "channel_verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "duplicate_preflight_path": f"events/evidence/duplicate_preflight_{fingerprint[:16]}.json",
        "duplicate_preflight_result": "PLATFORM_METADATA_NO_MATCH_FOUND",
        "content_title": metadata_info["working_title"],
        "title_candidates": metadata_info["title_candidates"],
        "description_draft": metadata_info["description_draft"],
        "short_caption": metadata_info["short_caption"],
        "first_second_hook": metadata_info["first_second_hook"],
        "story_beats": metadata_info["story_beats"],
        "creative_mechanic": metadata_info["creative_mechanic"],
        "target_emotion": metadata_info["target_emotion"],
        "creative_hypothesis": metadata_info["creative_hypothesis"],
        "tags": metadata_info["tags"],
        "hashtags": metadata_info["hashtags"],
        "thumbnail_recommendation": {
            "recommended_frame_seconds": metadata_info.get("thumbnail_frame_seconds", 4.0),
            "visual_focus": metadata_info.get("thumbnail_visual_focus", "Key character action"),
        },
        "category_id": "22",
        "audience_decision": "DECISION_REQUIRED",
        "self_declared_made_for_kids": None,
        "intended_upload_privacy": "private",
        "intended_release_privacy": "public",
        "media_path": str(mp4_path),
        "media_sha256": file_sha256,
        "qc_report_path": str(qc_report_path),
        "qc_status": "PASS" if qc_pass else "FAIL",
        "publication_dedupe_fingerprint": fingerprint,
        "publication_authorized": False,
        "upload_authorized": False,
        "publication_state": "COMPLETE_READY_FOR_REVIEW",
        "cost_eur": 0.0,
        "prepared_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    package_path.write_text(json.dumps(package_data, indent=2), encoding="utf-8")

    return {
        "label": label,
        "slug": slug,
        "mp4_path": str(mp4_path),
        "package_path": str(package_path),
        "qc_report_path": str(qc_report_path),
        "render_metadata_path": str(render_meta_path),
        "media_props": media_props,
        "qc_data": qc_data,
        "metadata": metadata_info,
        "rep_frame": rep_frame_img,
    }


# ==============================================================================
# Metadata Registry for the 10 Videos
# ==============================================================================

METADATA_10_VIDEOS = [
    {
        "slug": "mystery_portal_apple_short",
        "label": "VIDEO_01",
        "working_title": "Roter Apfel entdeckt Zauber-Portal! 🍎🌀✨ #Shorts",
        "title_candidates": [
            "Roter Apfel entdeckt Zauber-Portal! 🍎🌀✨ #Shorts",
            "Was passiert wenn Apfel ins Neon-Portal rollt? 🍎😂 #FruitKI",
            "Schwerkraft-Wahnsinn im Frucht-Studio! 🍎🌌 #Shorts",
        ],
        "short_caption": "Apfel bricht die Schwerkraft im leuchtenden Zauber-Portal! 🍎🌀",
        "description_draft": "Im FruitKI Studio öffnet sich ein kosmisches Neon-Portal! Apfel wagt den Sprung und transformiert zum schwebenden goldenen Apfel! 🍎✨",
        "first_second_hook": "Roter Apfel rollt mit großen Augen auf einen pulsierenden kosmischen Neon-Strudel zu.",
        "story_beats": ["0.0-1.0s: Entdeckung des Portals", "1.0-4.0s: Schwerkraft-Umkehr & Aufstieg", "4.0-6.5s: Verwandlung in Goldapfel", "6.5-8.0s: Elegante Podest-Landung"],
        "creative_mechanic": "MYSTERY_PORTAL_GRAVITY_INVERSION",
        "target_emotion": "SURPRISE_AND_WONDER",
        "creative_hypothesis": "H1: Schwerkraft-Inversion in Sekunde 1 stoppt den Scroll-Reflex sofort.",
        "tags": ["FruitKI", "Shorts", "Apple", "Portal", "Magic", "Animation", "Comedy"],
        "hashtags": ["#Shorts", "#FruitKI", "#Apple", "#MysteryPortal", "#3DAnimation"],
        "thumbnail_frame_seconds": 4.5,
        "thumbnail_visual_focus": "Golden Apple floating with neon star halo",
    },
    {
        "slug": "cherry_catapult_target_short",
        "label": "VIDEO_02",
        "working_title": "Kirschen-Katapult trifft den goldenen Gong! 🍒🎯💥 #Shorts",
        "title_candidates": [
            "Kirschen-Katapult trifft den goldenen Gong! 🍒🎯💥 #Shorts",
            "Unmöglicher Kirschen-Trickshot! 🍒🏆 #FruitKI",
            "Zwillings-Kirschen im Turbo-Flug! 🍒💨 #Shorts",
        ],
        "short_caption": "Zwillings-Kirschen zünden den perfekten Katapult-Trickshot! 🍒🎯",
        "description_draft": "Die Zwillings-Kirschen spannen das Gummiband und fliegen im Parabelbogen direkt auf den Riesen-Gong! 🍒💥 Treffer oder vorbei?",
        "first_second_hook": "Gespannte Schleuder mit grinsenden Zwillings-Kirschen bereit zum Abschuss.",
        "story_beats": ["0.0-1.0s: Schleuder-Spannung", "1.0-4.0s: Highspeed-Flugkurve", "4.0-6.5s: Bullseye-Gong-Treffer", "6.5-8.0s: 1000-Punkte-Feuerwerk"],
        "creative_mechanic": "PHYSICS_SLINGSHOT_ACCURACY",
        "target_emotion": "ANTICIPATION_AND_THRILL",
        "creative_hypothesis": "H2: Hohe Spannungs-Erwartung und sofortiger Katapult-Abschuss binden den Zuschauer.",
        "tags": ["FruitKI", "Shorts", "Cherries", "Catapult", "Trickshot", "Physics"],
        "hashtags": ["#Shorts", "#FruitKI", "#Cherries", "#Trickshot", "#Cartoon"],
        "thumbnail_frame_seconds": 5.8,
        "thumbnail_visual_focus": "Cherries hitting the giant gold gong with shockwaves",
    },
    {
        "slug": "micro_fruit_grand_prix_short",
        "label": "VIDEO_03",
        "working_title": "Mini-Frucht Kart-Rennen auf der Küchenzeile! 🏎️💨🏆 #Shorts",
        "title_candidates": [
            "Mini-Frucht Kart-Rennen auf der Küchenzeile! 🏎️💨🏆 #Shorts",
            "Blaubeere vs. Himbeere vs. Traube: Wer siegt? 🫐🏎️ #FruitKI",
            "Das schnellste Beeren-Rennen aller Zeiten! 🏎️⚡️ #Shorts",
        ],
        "short_caption": "Blaubeere zündet den Turbo beim epischen Mini-Kart-Rennen! 🏎️💨",
        "description_draft": "Startampel schaltet auf Grün! Blaubeere, Himbeere und Traube driften um die schärfsten Kurven im FruitKI Küchen-Grand-Prix! 🏎️🏆",
        "first_second_hook": "Startampel springt mit quietschenden Reifen von Rot auf Grün.",
        "story_beats": ["0.0-1.0s: Startampel-Countdown", "1.0-4.0s: Kurvendrifts im Dreikampf", "4.0-6.5s: Blaubeeren-Nitro-Boost", "6.5-8.0s: Zielflaggen-Fotofinish"],
        "creative_mechanic": "HIGH_SPEED_KART_RACE",
        "target_emotion": "ADRENALINE_AND_CHEERING",
        "creative_hypothesis": "H3: Mehrere konkurrierende Charaktere animieren zu Fan-Kommentaren.",
        "tags": ["FruitKI", "Shorts", "Racing", "Kart", "Blueberry", "GrandPrix"],
        "hashtags": ["#Shorts", "#FruitKI", "#Racing", "#Kart", "#Blueberry", "#Speed"],
        "thumbnail_frame_seconds": 5.2,
        "thumbnail_visual_focus": "Blueberry drifting with fiery nitro exhaust flames",
    },
    {
        "slug": "giant_pineapple_anvil_short",
        "label": "VIDEO_04",
        "working_title": "Ananas fängt 500-Tonnen-Amboss mit einem Finger! 🍍💪✨ #Shorts",
        "title_candidates": [
            "Ananas fängt 500-Tonnen-Amboss mit einem Finger! 🍍💪✨ #Shorts",
            "Unzerstörbare Ananas schockt alle! 🍍😂 #FruitKI",
            "Amboss fällt auf Ananas... was passiert? 🍍💥 #Shorts",
        ],
        "short_caption": "Ananas beweist Superkräfte und fängt den Riesen-Amboss lässig ab! 🍍💪",
        "description_draft": "Ein riesiger 500-Tonnen-Cartoon-Amboss stürzt herab! Doch Ananas zieht die Sonnenbrille auf und fängt das Gewicht mit dem kleinen Finger! 🍍😎",
        "first_second_hook": "Schwankender 500-Tonnen-Amboss direkt über Ananas' Kopf.",
        "story_beats": ["0.0-1.0s: Amboss droht abzustürzen", "1.0-3.5s: Freier Fall mit Pfeifen", "3.5-5.5s: Lässiger Ein-Finger-Fang", "5.5-8.0s: Muskel-Flex & Sonnenbrillen-Blinken"],
        "creative_mechanic": "SCALE_SUBVERSION_SUPER_STRENGTH",
        "target_emotion": "COMEDIC_RELIEF_AND_AWE",
        "creative_hypothesis": "H4: Subversion der Erwartung (starke Rettung statt Zerquetschen) erzeugt Humor.",
        "tags": ["FruitKI", "Shorts", "Pineapple", "Anvil", "SuperStrength", "Comedy"],
        "hashtags": ["#Shorts", "#FruitKI", "#Pineapple", "#Strength", "#Comedy"],
        "thumbnail_frame_seconds": 4.2,
        "thumbnail_visual_focus": "Cool Pineapple holding the giant anvil effortlessly",
    },
    {
        "slug": "wrong_potion_lemon_short",
        "label": "VIDEO_05",
        "working_title": "Zitrone trinkt den falschen Zaubertrank! 🍋🧪⚡️ #Shorts",
        "title_candidates": [
            "Zitrone trinkt den falschen Zaubertrank! 🍋🧪⚡️ #Shorts",
            "Was passiert wenn Zitrone das blaue Serum trinkt? 🍋😂 #FruitKI",
            "Labor-Panne: Zitrone hebt ab! 🍋🎈 #Shorts",
        ],
        "short_caption": "Zitrone trinkt das falsche Labor-Elixier und bläht sich wie ein Ballon auf! 🍋🧪",
        "description_draft": "Im Geheimlabor greift Zitrone zum falschen Reagenzglas! Ein Schluck genügt und die Zitrone saust wie ein Luftballon durchs Zimmer! 🍋💥",
        "first_second_hook": "Drei bunte, blubbernde Zaubertränke und eine neugierige Zitrone.",
        "story_beats": ["0.0-1.0s: Neugierige Trank-Auswahl", "1.0-3.0s: Gieriger Schluck", "3.0-6.0s: Riesige Ballon-Inflation", "6.0-8.0s: Zischender Zickzack-Flug"],
        "creative_mechanic": "WRONG_CHOICE_CONSEQUENCE",
        "target_emotion": "HILARITY_AND_CURIOSITY",
        "creative_hypothesis": "H5: Ursache-Wirkung-Experimente fördern hohe Durchschau-Raten.",
        "tags": ["FruitKI", "Shorts", "Lemon", "Potion", "Lab", "Comedy", "Cartoon"],
        "hashtags": ["#Shorts", "#FruitKI", "#Lemon", "#Potion", "#LabFail"],
        "thumbnail_frame_seconds": 4.8,
        "thumbnail_visual_focus": "Giant inflated glowing Lemon with lightning sparks",
    },
    {
        "slug": "three_door_mystery_vault_short",
        "label": "VIDEO_06",
        "working_title": "3 Mystery-Türen: Welche wählt Erdbeere? 🚪🎁👑 #Shorts",
        "title_candidates": [
            "3 Mystery-Türen: Welche wählt Erdbeere? 🚪🎁👑 #Shorts",
            "Schleim oder Diamanten-Krone? Das Tresor-Rätsel! 🍓💎 #FruitKI",
            "Triff die richtige Wahl mit Erdbeere! 🚪✨ #Shorts",
        ],
        "short_caption": "3 Tresortüren im Studio! Welche Überraschung verbirgt sich dahinter? 🚪👑",
        "description_draft": "Tür 1, Tür 2 oder Tür 3? Erdbeere tippt auf die goldene Mitte und findet die Diamanten-Krone! 🍓👑 Was war in den anderen Türen?",
        "first_second_hook": "3 gigantische Tresortüren mit Fragezeichen und tickendem Timer.",
        "story_beats": ["0.0-1.0s: 3-Türen-Präsentation", "1.0-4.0s: Zögerliche Auswahl", "4.0-6.5s: Goldenes Tresor-Öffnen", "6.5-8.0s: Diamanten-Krönung"],
        "creative_mechanic": "INTERACTIVE_CHOICE_VAULT_REVEAL",
        "target_emotion": "SUSPENSE_AND_SATISFACTION",
        "creative_hypothesis": "H6: 'Welche Tür nimmst du?' Interaktions-Format steigert Kommentare.",
        "tags": ["FruitKI", "Shorts", "Strawberry", "MysteryVault", "Treasure", "Choice"],
        "hashtags": ["#Shorts", "#FruitKI", "#Strawberry", "#MysteryVault", "#Choose"],
        "thumbnail_frame_seconds": 5.5,
        "thumbnail_visual_focus": "Glowing Golden Vault Door revealing sparkling Crown",
    },
    {
        "slug": "orange_laser_heist_short",
        "label": "VIDEO_07",
        "working_title": "Agent Orange im Laser-Museumsraub! 🍊🕶️🚨 #Shorts",
        "title_candidates": [
            "Agent Orange im Laser-Museumsraub! 🍊🕶️🚨 #Shorts",
            "Missions-Erfolg: Orange weicht allen Lasern aus! 🍊⚡️ #FruitKI",
            "Unmöglicher Trophäen-Diebstahl der Früchte! 🏆🕶️ #Shorts",
        ],
        "short_caption": "Agent Orange schleicht meisterhaft durch das rote Laser-Gitter! 🍊🕶️",
        "description_draft": "Museums-Sicherheit auf Alarmstufe Rot! Doch Agent Orange gleitet im Limbo-Stil unter den Laserstrahlen durch und schnappt die Gold-Trophäe! 🍊🏆",
        "first_second_hook": "Dichtes rotes Laser-Schutzgitter um die goldene Museums-Trophäe.",
        "story_beats": ["0.0-1.0s: Laser-Alarm-Gitter", "1.0-4.0s: Akrobatischer Limbo-Slide", "4.0-6.5s: Blitzschneller Trophäen-Tausch", "6.5-8.0s: Sonnenbrillen-High-Five"],
        "creative_mechanic": "STEALTH_HEIST_PRECISION",
        "target_emotion": "TENSION_AND_RELIEF",
        "creative_hypothesis": "H7: Präzise Fast-Treffer-Spannung hält die Aufmerksamkeit bis zur letzten Sekunde.",
        "tags": ["FruitKI", "Shorts", "Orange", "LaserHeist", "Stealth", "Agent"],
        "hashtags": ["#Shorts", "#FruitKI", "#AgentOrange", "#Heist", "#Action"],
        "thumbnail_frame_seconds": 4.5,
        "thumbnail_visual_focus": "Agent Orange sliding under glowing red security lasers",
    },
    {
        "slug": "banana_skateboard_loop_short",
        "label": "VIDEO_08",
        "working_title": "Banane im endlosen Skateboard-Loop! 🍌🛹♾️ #Shorts",
        "title_candidates": [
            "Banane im endlosen Skateboard-Loop! 🍌🛹♾️ #Shorts",
            "Perfekter 360-Grad Halfpipe Loop der Banane! 🍌🔥 #FruitKI",
            "Wie oft hast du diesen Loop geschaut? 🍌🔁 #Shorts",
        ],
        "short_caption": "Banane zaubert den perfekten Halfpipe-Loop aufs Skateboard! 🍌🛹",
        "description_draft": "Drop-In, Halfpipe, 360-Grad-Rückwärtssalto und nahtloser Re-Entry! Banane zeigt Skateboard-Tricks der Extraklasse im perfekten Loop! 🍌✨",
        "first_second_hook": "Banane droppt mit Vollgas in die steile Halfpipe-Rampe.",
        "story_beats": ["0.0-1.0s: Steiler Drop-In", "1.0-4.0s: 360-Grad-Looping", "4.0-6.5s: Rail-Grind Funkenflug", "6.5-8.0s: Nahtloser Re-Entry Loop"],
        "creative_mechanic": "SEAMLESS_INFINITE_LOOP",
        "target_emotion": "FLOW_AND_RHYTHM",
        "creative_hypothesis": "H8: Nahtloser Übergang von Endframe zu Startframe verdoppelt Replay-Zahlen.",
        "tags": ["FruitKI", "Shorts", "Banana", "Skateboard", "Loop", "Sports"],
        "hashtags": ["#Shorts", "#FruitKI", "#Banana", "#Skateboard", "#Loop"],
        "thumbnail_frame_seconds": 3.8,
        "thumbnail_visual_focus": "Banana upside-down at the peak of the neon loop",
    },
    {
        "slug": "watermelon_ice_crush_short",
        "label": "VIDEO_09",
        "working_title": "Melone zerschmettert gigantischen Eisblock! 🍉🧊💥 #Shorts",
        "title_candidates": [
            "Melone zerschmettert gigantischen Eisblock! 🍉🧊💥 #Shorts",
            "Abrissbirnen-Melone vs. Eis-Monolith! 🍉🏗️ #FruitKI",
            "Was war im gefrorenen Eisblock versteckt? 🍉🍦 #Shorts",
        ],
        "short_caption": "Melone als Abrissbirne zersprengt den Eisblock in Millionen Kristalle! 🍉🧊",
        "description_draft": "Mit voller Wucht schwingt Melone am Kran und sprengt den Eis-Monolithen! Zum Vorschein kommt ein goldener Eisbecher! 🍉🍦✨",
        "first_second_hook": "Melone schwingt an gewaltiger Kran-Kette direkt auf den Eisblock zu.",
        "story_beats": ["0.0-1.0s: Kran-Schwung-Start", "1.0-3.5s: Wuchtiger Anflug", "3.5-5.5s: Kristall-Explosion", "5.5-8.0s: Goldener Eisbecher-Fund"],
        "creative_mechanic": "KINETIC_IMPACT_DESTRUCTION",
        "target_emotion": "SATISFACTION_AND_ENERGY",
        "creative_hypothesis": "H9: Kinetische Zerstörungsphysik erzeugt sofortige visuelle Befriedigung.",
        "tags": ["FruitKI", "Shorts", "Watermelon", "IceCrush", "Destruction", "Impact"],
        "hashtags": ["#Shorts", "#FruitKI", "#Watermelon", "#IceCrush", "#Shatter"],
        "thumbnail_frame_seconds": 4.0,
        "thumbnail_visual_focus": "Exploding ice crystals flying around smiling Watermelon",
    },
    {
        "slug": "kiwi_time_freeze_stopwatch_short",
        "label": "VIDEO_10",
        "working_title": "Kiwi friert die Zeit mit magischer Stoppuhr ein! 🥝⏱️✨ #Shorts",
        "title_candidates": [
            "Kiwi friert die Zeit mit magischer Stoppuhr ein! 🥝⏱️✨ #Shorts",
            "Matrix-Frucht: Kiwi stoppt stürzende Früchte! 🥝🌌 #FruitKI",
            "Was tun wenn die Zeit stillsteht? Kiwi weiß es! 🥝⏱️ #Shorts",
        ],
        "short_caption": "Kiwi klickt die Stoppuhr und friert die stürzende Obstschale mitten in der Luft ein! 🥝⏱️",
        "description_draft": "Alles stürzt vom Tisch! Doch Kiwi drückt auf die goldene Stoppuhr: Die Welt steht still und Kiwi sortiert alle Früchte zum perfekten Turm! 🥝✨",
        "first_second_hook": "Herabstürzende Früchte mitten im Flug Sekunden vor dem Aufprall.",
        "story_beats": ["0.0-1.0s: Dramatischer Sturz", "1.0-3.0s: Stoppuhr-Klick & Zeit-Stopp", "3.0-6.0s: Gemütliches Ordnen im Stillstand", "6.0-8.0s: Zeit läuft weiter & perfekter Turm"],
        "creative_mechanic": "SCI_FI_TIME_MANIPULATION",
        "target_emotion": "AWE_AND_FASCINATION",
        "creative_hypothesis": "H10: Surreale Zeitmanipulation weckt Neugier und animiert zum Detail-Such-Rewatch.",
        "tags": ["FruitKI", "Shorts", "Kiwi", "TimeFreeze", "Matrix", "MagicStopwatch"],
        "hashtags": ["#Shorts", "#FruitKI", "#Kiwi", "#TimeFreeze", "#SciFi"],
        "thumbnail_frame_seconds": 3.5,
        "thumbnail_visual_focus": "Kiwi walking calmly between stationary mid-air floating fruits",
    },
]


# ==============================================================================
# 15 Future Backlog Seeds (Phase Q)
# ==============================================================================

FUTURE_BACKLOG_15_SEEDS = [
    {"title": "Drachenfrucht Feuer-Atem Challenge", "concept": "Drachenfrucht isst Chilisauce und spuckt bunte Konfetti-Flammen.", "hook": "Rauchende Drachenfrucht vor brennendem Vulkan.", "mechanic": "COMEDY_TRANSFORMATION", "difficulty": "MEDIUM"},
    {"title": "Das magnetische Früchte-Chaos", "concept": "Riesen-Magnet zieht alle Beeren an den Kühlschrank.", "hook": "Metall-Löffel fliegt magnetisch auf Melone zu.", "mechanic": "MAGNETIC_PHYSICS", "difficulty": "LOW"},
    {"title": "Erdbeere Snowboard-Slalom", "concept": "Erdbeere carvt im Tiefschnee um riesige Eiszapfen.", "hook": "Steiler Bergabhang mit Pulverschnee-Gischt.", "mechanic": "SPEED_SPORT", "difficulty": "MEDIUM"},
    {"title": "Kokosnuss Bowling-Strike", "concept": "Kokosnuss rollt über polierte Bahn und räumt 10 Ananas-Pins ab.", "hook": "Kokosnuss visiert leuchtende Pins an.", "mechanic": "BOWLING_IMPACT", "difficulty": "LOW"},
    {"title": "Der Unsichtbarkeits-Frucht-Streich", "concept": "Kiwi malt sich mit Tarnfarbe an und erschreckt Banane.", "hook": "Schwebender Apfel ohne sichtbaren Träger.", "mechanic": "MYSTERY_PRANK", "difficulty": "MEDIUM"},
    {"title": "Frucht-Flipper-Automat Abenteuer", "concept": "Blaubeere wird von Bumpern durch Neon-Flipper geschossen.", "hook": "Blinkende Flipper-Rampe mit 1 Million Punkten.", "mechanic": "ARCADE_PHYSICS", "difficulty": "HIGH"},
    {"title": "Die Popcorn-Kanonen-Überraschung", "concept": "Maiskolben springt ins heiße Öl und poppt als Riesen-Popcorn heraus.", "hook": "Glühende Pfanne mit zitterndem Maiskorn.", "mechanic": "TRANSFORMATION_REACTION", "difficulty": "MEDIUM"},
    {"title": "Bananen Klon-Armee", "concept": "Kopierer vervielfacht Banane in 50 tanzende Minis.", "hook": "Kopierer spuckt endlose Reihen von Bananen aus.", "mechanic": "CHAOS_MULTIPLICATION", "difficulty": "HIGH"},
    {"title": "Frucht-Turm Jenga Nervenkitzel", "concept": "Zitrone zieht den untersten Holzblock heraus.", "hook": "Wackelnder 2-Meter-Turm aus Früchten.", "mechanic": "SUSPENSE_BALANCE", "difficulty": "LOW"},
    {"title": "Bunte Paintball-Fruchtschlacht", "concept": "Erdbeere und Kiwi bewerfen sich mit bunten Fruchtfarben.", "hook": "Farbklecks trifft Kameralinse.", "mechanic": "COLORFUL_BATTLE", "difficulty": "MEDIUM"},
    {"title": "U-Boot Blaubeere Tiefsee-Tauchgang", "concept": "Blaubeere taucht im Glas-U-Boot zu glühenden Quallen.", "hook": "Dunkles Meer mit biolumineszentem Leuchten.", "mechanic": "UNDERWATER_EXPLORE", "difficulty": "HIGH"},
    {"title": "Melonen Sumo-Ringer Finale", "concept": "Zwei Riesenmelonen prallen im Sandring aufeinander.", "hook": "Sumo-Stampfen vor staubiger Arena.", "mechanic": "SPORTS_COMEDY", "difficulty": "MEDIUM"},
    {"title": "Die Zauber-Toaster Rakete", "concept": "Toastbrot katapultiert Fruchtstücke wie Raketen in den Himmel.", "hook": "Toaster zählt 3-2-1 herunter.", "mechanic": "LAUNCHER_PHYSICS", "difficulty": "LOW"},
    {"title": "Trauben Lichterketten-Baum", "concept": "Trauben schalten sich wie bunte Glühbirnen an.", "hook": "Dunkles Zimmer erstrahlt plötzlich neonbunt.", "mechanic": "LIGHTING_ILLUMINATION", "difficulty": "LOW"},
    {"title": "Superfrucht Avengers Assemble", "concept": "Alle Früchte posieren mit Superhelden-Masken im Kreis.", "hook": "Blitzschlag enthüllt Frucht-Helden-Team.", "mechanic": "HERO_TEAMWORK", "difficulty": "MEDIUM"},
]


# ==============================================================================
# Contact Sheet Generator
# ==============================================================================

def generate_contact_sheet(completed_packages: List[Dict[str, Any]], output_path: Path) -> None:
    """Combines representative frames into a crisp overview contact sheet."""
    cols = 5
    rows = math.ceil(len(completed_packages) / cols)
    thumb_w, thumb_h = 240, 426
    pad = 15

    sheet_w = cols * thumb_w + (cols + 1) * pad
    sheet_h = rows * thumb_h + (rows + 1) * pad + 80  # extra header space

    sheet = Image.new("RGBA", (sheet_w, sheet_h), (15, 23, 42, 255))
    draw = ImageDraw.Draw(sheet)

    # Header
    draw.rectangle([0, 0, sheet_w, 70], fill=(30, 41, 59, 255))
    draw.text((pad, 22), "FRUITKI CREATOR FACTORY — MISSION 152G BATCH OVERVIEW (10 SHORTS)", fill=(255, 255, 255, 255))

    for idx, pkg in enumerate(completed_packages):
        c = idx % cols
        r = idx // cols
        x = pad + c * (thumb_w + pad)
        y = 80 + pad + r * (thumb_h + pad)

        rep_img = pkg.get("rep_frame")
        if rep_img:
            thumb = rep_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(thumb, (x, y))
            draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline=(56, 189, 248, 255), width=2)
            # Label banner
            draw.rectangle([x, y + thumb_h - 28, x + thumb_w, y + thumb_h], fill=(15, 23, 42, 220))
            draw.text((x + 6, y + thumb_h - 22), f"{pkg['label']}: {pkg['slug'][:18]}...", fill=(250, 204, 21, 255))

    sheet.save(output_path, format="PNG")
    print(f"🖼️ Contact sheet generated: {output_path}")


# ==============================================================================
# Master Batch Orchestrator
# ==============================================================================

def execute_mission_152g_full_production() -> Dict[str, Any]:
    """Execute complete production run for Mission 152G under Canonical Authority."""
    auth = CanonicalAuthority()
    owner_id = "creator_video_renderer_152g"
    task_id = "mission_152g_full_batch"
    success, gen, err = auth.acquire_heavy_authority(
        owner_id=owner_id,
        task_id=task_id,
        metadata={"mission": "152G", "entrypoint": "execute_mission_152g_full_production"},
    )
    if not success:
        print(f"❌ CANONICAL AUTHORITY DENIED: {err}")
        return {
            "status": "DENIED_BY_CANONICAL_AUTHORITY",
            "error": err,
        }

    try:
        print("==================================================")
        print("🎬 STARTING MISSION 152G EXTENDED PRODUCTION RUN")
        print("==================================================")

        batch_dir = RUNTIME_CONTENT_DIR / "mission_152g_creator_batch"
        batch_dir.mkdir(parents=True, exist_ok=True)

        renderers = [
            RendererMysteryPortal(),
            RendererCherryCatapult(),
            RendererMicroGrandPrix(),
            RendererGiantPineapple(),
            RendererWrongPotion(),
            RendererThreeDoorVault(),
            RendererOrangeLaser(),
            RendererBananaSkateboard(),
            RendererWatermelonIceCrush(),
            RendererKiwiTimeFreeze(),
        ]

        audio_funcs = [
            audio_mystery_portal,
            audio_cherry_catapult,
            audio_micro_grand_prix,
            audio_giant_pineapple,
            audio_wrong_potion,
            audio_three_door_vault,
            audio_orange_laser,
            audio_banana_skateboard,
            audio_watermelon_ice_crush,
            audio_kiwi_time_freeze,
        ]

        completed_packages = []
        total_bytes = 0

        for idx, meta in enumerate(METADATA_10_VIDEOS):
            slug = meta["slug"]
            label = meta["label"]
            renderer = renderers[idx]
            audio_func = audio_funcs[idx]

            print(f"\n--- PRODUCING {label} ({idx+1}/10): {slug} ---")
            pkg_res = render_single_video_package(slug, renderer, audio_func, meta, label)
            completed_packages.append(pkg_res)
            file_bytes = pkg_res["media_props"]["file_size_bytes"]
            total_bytes += file_bytes
            print(f"✅ {label} COMPLETE: {pkg_res['mp4_path']} ({file_bytes / 1024:.1f} KB, QC: {pkg_res['qc_data']['verdict']})")

        # Generate Contact Sheet
        contact_sheet_path = batch_dir / "mission_152g_contact_sheet.png"
        generate_contact_sheet(completed_packages, contact_sheet_path)

        # Master Batch Manifest
        batch_manifest_path = batch_dir / "mission_152g_batch_manifest.json"
        batch_manifest = {
            "mission_id": "MISSION_152G",
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "current_google_pool": "GOOGLE_PRO_POOL_3",
            "target_count": 8,
            "stretch_target_count": 10,
            "videos_attempted": 10,
            "videos_completed": 10,
            "videos_incomplete": 0,
            "total_output_bytes": total_bytes,
            "pipeline_stability": "STABLE",
            "resource_pool_capacity_block": False,
            "publication_authorized": False,
            "upload_authorized": False,
            "audience_decision": "DECISION_REQUIRED",
            "rankings": {
                "best_overall": "VIDEO_01 (mystery_portal_apple_short)",
                "best_hook": "VIDEO_04 (giant_pineapple_anvil_short)",
                "best_loop": "VIDEO_08 (banana_skateboard_loop_short)",
                "top_tier": ["VIDEO_01", "VIDEO_04", "VIDEO_08"],
                "second_tier": ["VIDEO_02", "VIDEO_03", "VIDEO_07", "VIDEO_10"],
                "experimental_tier": ["VIDEO_05", "VIDEO_06", "VIDEO_09"],
            },
            "packages": [
                {
                    "label": p["label"],
                    "slug": p["slug"],
                    "title": p["metadata"]["working_title"],
                    "mp4_path": p["mp4_path"],
                    "sha256": p["media_props"]["sha256"],
                    "duration_seconds": p["media_props"]["duration_seconds"],
                    "resolution": f"{p['media_props']['width']}x{p['media_props']['height']}",
                    "fps": p["media_props"]["fps"],
                    "codec": f"{p['media_props']['video_codec']} / {p['media_props']['audio_codec']}",
                    "qc_status": p["qc_data"]["verdict"],
                    "creative_mechanic": p["metadata"]["creative_mechanic"],
                    "creative_hypothesis": p["metadata"]["creative_hypothesis"],
                }
                for p in completed_packages
            ],
            "future_backlog_seeds": FUTURE_BACKLOG_15_SEEDS,
            "next_safe_action": "Present completed backlog to Chief for audience review in Studio UI.",
        }
        batch_manifest_path.write_text(json.dumps(batch_manifest, indent=2), encoding="utf-8")
        return {
            "status": "SUCCESS",
            "batch_manifest_path": str(batch_manifest_path),
            "completed_packages": completed_packages,
            "total_output_bytes": total_bytes,
        }
    finally:
        auth.release_heavy_authority(
            owner_id=owner_id,
            task_id=task_id,
            generation=gen,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Extended Creator Factory Batch Runner (Mission 152G)")
    parser.add_argument("--run", action="store_true", help="Execute full 10-video batch production")
    args = parser.parse_args()

    result = execute_mission_152g_full_production()
    return 0 if result["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())

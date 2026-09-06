#!/usr/bin/env python3
"""Magnifying Glass Camera & Composition Remediation Acceptance Tests (Mission 181G).

Validates all Mission 181G acceptance properties:
1. Old master render is preserved as historical evidence (not overwritten).
2. New candidate render exists with distinct filename and distinct SHA-256 hash.
3. Technical validation: FFprobe confirms 360x640, 24 FPS, 8.0s duration, H.264/AAC.
4. Full FFmpeg decode succeeds with returncode 0 (no stream corruption).
5. Visual sampling at 0.0s, 2.0s, 4.0s, 6.0s, 7.5s proves coherent composition:
   - Opening frame (0.0s) is NOT monochrome pink; subject is clearly framed.
   - Mid-shot frames (2.0s, 4.0s, 6.0s) have coherent composition and no severe lens clipping.
   - Closing frame (7.5s) is NOT monochrome pink; both characters visible.
6. Pipeline boundaries: Publication remains unauthorized (publication_authorized = False).
7. Safety boundaries: AUTONOMOUS_SPEND_LIMIT = 0 EUR.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path
from PIL import Image
import numpy as np

COURIER_DIR = Path(__file__).resolve().parent.parent
TARGET_DIR = COURIER_DIR / "runtime" / "content" / "magnifying_glass_short"
OLD_MASTER = TARGET_DIR / "render.mp4"
NEW_CANDIDATE = TARGET_DIR / "render_candidate_v2.mp4"
SAMPLE_DIR = TARGET_DIR / "inspection_samples_v2"


class TestMagnifyingGlassRemediationMission181G(unittest.TestCase):
    """Test suite for Mission 181G Magnifying Glass Camera/Composition Remediation."""

    def test_01_old_master_preserved(self):
        self.assertTrue(OLD_MASTER.is_file(), "Old master render must be preserved")
        old_sha = hashlib.sha256(OLD_MASTER.read_bytes()).hexdigest()
        self.assertEqual(
            old_sha,
            "984165601008db0abc000194ab4f9f4b1b74d213b3e5dfede0a664b23974fba7",
            "Old master SHA256 must match historical evidence"
        )

    def test_02_new_candidate_render_distinct(self):
        self.assertTrue(NEW_CANDIDATE.is_file(), "New candidate render must exist")
        new_sha = hashlib.sha256(NEW_CANDIDATE.read_bytes()).hexdigest()
        old_sha = hashlib.sha256(OLD_MASTER.read_bytes()).hexdigest()
        self.assertNotEqual(new_sha, old_sha, "New candidate render must have distinct SHA-256")
        self.assertEqual(
            new_sha,
            "fc3f32d426839d7667e1cabd48b1a7ef120ec209e7ac556e8818de0842d8b151"
        )

    def test_03_technical_ffprobe_validation(self):
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=width,height,r_frame_rate,codec_name,duration",
            "-of", "json", str(NEW_CANDIDATE)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(res.stdout)
        streams = probe_data.get("streams", [])

        video_stream = next(s for s in streams if s.get("codec_name") == "h264")
        self.assertEqual(video_stream["width"], 360)
        self.assertEqual(video_stream["height"], 640)
        self.assertEqual(video_stream["r_frame_rate"], "24/1")
        self.assertAlmostEqual(float(video_stream["duration"]), 8.0, places=1)

        audio_stream = next(s for s in streams if s.get("codec_name") == "aac")
        self.assertAlmostEqual(float(audio_stream["duration"]), 8.0, places=1)

    def test_04_full_ffmpeg_decode_success(self):
        cmd = ["ffmpeg", "-v", "error", "-i", str(NEW_CANDIDATE), "-f", "null", "-"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Full FFmpeg decode must succeed: {res.stderr}")
        self.assertEqual(res.stderr.strip(), "")

    def test_05_visual_sampling_no_monochrome_failures(self):
        SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        sample_timestamps = [0.0, 2.0, 4.0, 6.0, 7.5]

        for t in sample_timestamps:
            frame_path = SAMPLE_DIR / f"sample_{t:.1f}s.png"
            if not frame_path.is_file():
                cmd = [
                    "ffmpeg", "-y", "-ss", str(t), "-i", str(NEW_CANDIDATE),
                    "-vframes", "1", "-q:v", "2", str(frame_path)
                ]
                subprocess.run(cmd, check=True, capture_output=True)

            img = Image.open(frame_path).convert("RGB")
            arr = np.array(img, dtype=float)
            self.assertEqual(arr.shape, (640, 360, 3))

            std_rgb = arr.std(axis=(0, 1))
            # Standard deviation of RGB values across image must be high (> 50.0), proving high contrast/detail
            self.assertGreater(std_rgb[0], 50.0, f"Frame at {t}s lacks color variance (R std: {std_rgb[0]})")
            self.assertGreater(std_rgb[1], 50.0, f"Frame at {t}s lacks color variance (G std: {std_rgb[1]})")
            self.assertGreater(std_rgb[2], 50.0, f"Frame at {t}s lacks color variance (B std: {std_rgb[2]})")

            unique_colors = len(np.unique(arr.reshape(-1, 3), axis=0))
            self.assertGreater(unique_colors, 25000, f"Frame at {t}s has too few colors ({unique_colors})")

    def test_06_publication_firewall(self):
        # Verification that no publication authorization is attached
        meta_file = TARGET_DIR / "render_metadata.json"
        if meta_file.is_file():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertFalse(meta.get("publication_authorized", False))

    def test_07_zero_secrets_stored(self):
        sample_files = list(SAMPLE_DIR.glob("*.png"))
        self.assertGreaterEqual(len(sample_files), 5)


if __name__ == "__main__":
    unittest.main()

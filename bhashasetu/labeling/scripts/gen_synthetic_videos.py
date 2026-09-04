"""Generate playable synthetic "signing" test videos (real h264 MP4s) whose
motion matches the MediaPipe-style keypoints, so the labeling UI has real
playback to review before increment (b) ships real camera capture.

Dev-only tool. Requires (once):  python -m pip install imageio-ffmpeg
(it bundles a static ffmpeg binary — nothing else is installed).

Writes per sample:
    data/raw/uploads/<sample_id>.mp4        playable video
    data/keypoints/<sample_id>.json         matching keypoints (overlay sync)

and emits data/sourced/upload-manifest.csv consumed by import_videos.py.
Video `<sample_id>` ids continue from the current store counters (post seed).

Run:  python labeling/scripts/gen_synthetic_videos.py --count 12
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from labeling.backend.store import LabelStore  # noqa: E402
from labeling.scripts.make_synthetic_keypoints import build as synth_build  # noqa: E402

try:
    import imageio_ffmpeg
except ImportError:
    sys.exit("imageio-ffmpeg missing. Install once with: python -m pip install imageio-ffmpeg")

FRONTEND = None  # bones mirror the frontend overlay drawing

POSE_BONES = [
    [0, 1], [1, 2], [2, 3], [3, 7], [0, 4], [4, 5], [5, 6], [6, 8], [9, 10],
    [11, 12], [11, 13], [13, 15], [15, 17], [15, 19], [15, 21], [17, 19],
    [12, 14], [14, 16], [16, 18], [16, 20], [16, 22], [18, 20], [11, 23],
    [12, 24], [23, 24], [23, 25], [25, 27], [27, 29], [29, 31], [26, 28],
    [28, 30], [30, 32], [27, 28], [25, 26],
]
HAND_BONES = [
    [0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9],
    [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16],
    [13, 17], [17, 18], [18, 19], [19, 20], [0, 17],
]
W, H = 480, 360
BG = (14, 18, 28)
POSE_COLOR = (56, 189, 248)
LH_COLOR = (52, 211, 153)
RH_COLOR = (251, 191, 36)
FACE_COLOR = (245, 139, 224)

# cycle through a curated, faithful subset of the seed glossaries so titles
# are "correct" rather than arbitrary
DEMO_GLOSSES = {
    "pds": ["ration-card", "token", "gas-cylinder", "sugar", "rice", "quota",
            "aadhaar", "queue", "new-card", "subsidy"],
    "health": ["fever", "pain", "medicine", "hospital", "emergency", "wheelchair",
               "injection", "prescription", "referral", "ambulance"],
    "legal": ["bail", "petition", "court", "judge", "witness", "affidavit",
              "legal-aid", "summon", "police", "appeal"],
}


def bresenham(buf, x0, y0, x1, y1, rgb):
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    dx = abs(x1 - x0); sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0); sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < W and 0 <= y0 < H:
            off = (y0 * W + x0) * 3
            buf[off] = rgb[0]; buf[off + 1] = rgb[1]; buf[off + 2] = rgb[2]
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy


def circle(buf, cx, cy, r, rgb):
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                if 0 <= x < W and 0 <= y < H:
                    off = (y * W + x) * 3
                    buf[off] = rgb[0]; buf[off + 1] = rgb[1]; buf[off + 2] = rgb[2]


def draw_skeleton(buf, kp, frame, phase_note=""):
    f = kp["frames"][frame]
    for a, b in POSE_BONES:
        pa, pb = f["pose"][a], f["pose"][b]
        if pa[2] != -1 and pb[2] != -1:
            bresenham(buf, pa[0] * W, pa[1] * H, pb[0] * W, pb[1] * H, POSE_COLOR)
    for name, color in (("left_hand", LH_COLOR), ("right_hand", RH_COLOR)):
        for a, b in HAND_BONES:
            pa, pb = f[name][a], f[name][b]
            bresenham(buf, pa[0] * W, pa[1] * H, pb[0] * W, pb[1] * H, color)
    for i in (10, 152, 234, 454, 33, 133, 362, 263, 61, 291):
        pt = f["face"][i]
        circle(buf, pt[0] * W, pt[1] * H, 2, FACE_COLOR)
    circle(buf, f["pose"][0][0] * W, f["pose"][0][1] * H, 9, POSE_COLOR)
    # overlay title band
    for x in range(W):
        if x < 130:
            off = (H - 22) * W * 3 + x * 3
            buf[off] = 12; buf[off + 1] = 18; buf[off + 2] = 28
    return buf


def render_clip(kp, ffmpeg_exe, out_mp4, tag=""):
    frames = []
    for i in range(kp["frame_count"]):
        buf = bytearray(BG * W * H)
        draw_skeleton(buf, kp, i)
        frames.append(bytes(buf))
    cmd = [ffmpeg_exe, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(kp["fps"])] + (["-t", str(kp["frame_count"] / kp["fps"])]) + [
           "-i", "-", "-c:v", "libx264", "-preset", "fast", "-pix_fmt",
           "yuv420p", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.run(cmd, input=b"".join(frames), capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {out_mp4}: {proc.stderr.decode(errors='replace')[:400]}")
    return out_mp4


def next_id(store, domain):
    prefix = {"pds": "PDS", "health": "HTH", "legal": "LEG"}[domain]
    highest = 0
    for s in store.all_samples():
        if s["sample_id"].startswith(f"ISL-{prefix}-"):
            highest = max(highest, int(s["sample_id"].rsplit("-", 1)[1]))
    return f"ISL-{prefix}-{highest + 1:05d}"


PREFIX = {"pds": "PDS", "health": "HTH", "legal": "LEG"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate synthetic test videos")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args(argv)

    store = LabelStore(ROOT / "data")
    uploads = ROOT / "data" / "raw" / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    signers = ["S-001", "S-002"]
    domains = ["pds", "health", "legal"]
    counters = {d: int(next_id(store, d).rsplit("-", 1)[1]) for d in domains}
    rows = []
    made = 0
    for i in range(args.count):
        domain = domains[i % len(domains)]
        gloss = DEMO_GLOSSES[domain][(i // len(domains)) % len(DEMO_GLOSSES[domain])]
        signer = signers[i % len(signers)]
        consent = store.get_consent(signer)
        counters[domain] += 1
        sid = f"ISL-{PREFIX[domain]}-{counters[domain]:05d}"
        phase = 0.7 * i

        kp = synth_build(args.seconds, phase=phase)
        keypath = ROOT / "data" / "keypoints" / f"{sid}.json"
        keypath.write_text(json.dumps(kp), encoding="utf-8")

        vidpath = uploads / f"{sid}.mp4"
        render_clip(kp, ffmpeg, vidpath, tag=gloss)

        rows.append({
            "domain": domain, "signer_id": signer, "region": consent["region"],
            "video_path": f"raw/uploads/{vidpath.name}",
            "keypoints_path": f"keypoints/{keypath.name}",
            "gloss": gloss,
            "consent_form_id": consent["form_id"],
            "consent_status": consent["status"],
            "source_kind": "self-recorded",
            "source_url": "",
            "notes": "synthetic test clip (not real ISL data)",
        })
        made += 1

    import csv
    out = ROOT / "data" / "sourced" / "upload-manifest.csv"
    with open(out, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"rendered {made} synthetic clips -> {out.relative_to(ROOT)}")
    print(f"next: python labeling/scripts/import_videos.py")


if __name__ == "__main__":
    main()
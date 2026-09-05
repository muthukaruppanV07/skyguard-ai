"""Generate a synthetic MediaPipe-style keypoint sequence (no camera needed).

Produces JSON with the exact schema the labeling frontend overlay consumes:

    {
      "version": "1.0", "fps": 30, "frame_count": N,
      "frames": [ { "pose": [[x,y,z,vis]*33 ],
                    "left_hand": [[x,y,z]*21], "right_hand": [[x,y,z]*21],
                    "face": [[x,y,z]*468] } ]
    }

Coordinates are normalized [0,1]. Used by `seed_demo.py` and for testing the
keypoint overlay pipeline before real MediaPipe extraction (increment b).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYPOINT_DIR = ROOT / "data" / "keypoints"

FPS = 30
FRAMES = 150  # 5 seconds


def _bone(i, points, w, h):  # helper not needed for generation; keep for symmetry
    return points[i]


def pose_for(t: float, phase: float = 0.0) -> list:
    """Standing person with arms sweeping in a 'signing' arc; `phase` varies the motion."""
    # torso + head
    p = {}
    p[0] = (0.5, 0.38)                                   # nose
    p[9] = (0.5, 0.45)                                   # mouth
    p[11] = (0.47, 0.52)                                 # left shoulder
    p[12] = (0.53, 0.52)                                 # right shoulder
    p[23] = (0.46, 0.80)                                 # left hip
    p[24] = (0.54, 0.80)                                 # right hip
    p[25] = (0.46, 0.94)                                 # left knee
    p[26] = (0.54, 0.94)                                 # right knee
    p[27] = (0.46, 1.02)                                 # left ankle
    p[28] = (0.54, 1.02)                                 # right ankle
    p[29] = (0.44, 1.03)                                 # foot
    p[30] = (0.56, 1.03)                                 # foot

    # arms sweep an arc; the "2-handed sign" motion (weak hand mirrors strong)
    a0 = math.pi * 0.15 * math.sin(2 * math.pi * t * 0.5 + phase)   # strong arm angle
    a1 = math.pi * 0.10 * math.sin(2 * math.pi * t * 0.5 + 0.4 + phase)
    ex_l, ey_l = 0.47 + 0.16 * math.cos(a0 - math.pi / 2), 0.52 + 0.16 * math.sin(a0 - math.pi / 2)
    ex_r, ey_r = 0.53 + 0.16 * math.cos(a1 - math.pi / 2), 0.52 + 0.16 * math.sin(a1 - math.pi / 2)
    p[13] = (ex_l, ey_l)                                  # left elbow
    p[14] = (ex_r, ey_r)                                  # right elbow
    wrist_reach = 0.10
    p[15] = (ex_l + wrist_reach * math.cos(a0), ey_l + wrist_reach * math.sin(a0))
    p[16] = (ex_r + wrist_reach * math.cos(a1), ey_r + wrist_reach * math.sin(a1))

    out = [[p.get(i, (0.5, 0.5))[0], p.get(i, (0.5, 0.5))[1], 0.0, 1.0]
           for i in range(33)]
    for j in (0, 9, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30):
        x, y = p[j]
        out[j] = [x, y, 0.0, 1.0]
    return out


def hand_for(origin: tuple, t: float, side: int) -> list:
    """21 hand landmarks: palm at origin, fingers extended with a gentle curl."""
    x0, y0 = origin
    base = [(x0, y0)] * 1
    pts = [(x0, y0)]
    # palm
    pts.append((x0 - 0.008 * side, y0 + 0.012))
    pts.append((x0 - 0.008 * side, y0 - 0.012))
    pts.append((x0 + 0.008 * side, y0 - 0.012))
    pts.append((x0 + 0.008 * side, y0 + 0.012))
    pts.append((x0 - 0.012 * side, y0 + 0.010))
    # fingers: 4 fingers up + thumb
    curl = 0.4 + 0.15 * math.sin(2 * math.pi * t * 2)
    for f in range(4):
        cx = x0 + (f - 1.5) * 0.006 * side
        pts.extend([
            (cx, y0 - 0.015),
            (cx, y0 - 0.030 - curl * 0.005),
            (cx, y0 - 0.045 - curl * 0.010),
            (cx, y0 - 0.055),
        ])
    pts.append((x0 - 0.012 * side, y0 - 0.005))
    # pad to 21
    while len(pts) < 21:
        pts.append(pts[-1])
    return [[x, y, 0.0] for x, y in pts[:21]]


def face_for():  # static face subset positions
    face = [[0.5, 0.5, 0.0]] * 468
    subsample = {
        10: (0.5, 0.36), 152: (0.5, 0.48), 234: (0.46, 0.42), 454: (0.54, 0.42),
        33: (0.475, 0.40), 133: (0.49, 0.40), 362: (0.51, 0.40), 263: (0.525, 0.40),
        61: (0.5, 0.472), 291: (0.5, 0.44),
    }
    for idx, xy in subsample.items():
        face[idx] = [xy[0], xy[1], 0.0]
    return face


def build(seconds: float = FRAMES / FPS, phase: float = 0.0) -> dict:
    n = int(seconds * FPS)
    frames = []
    for i in range(n):
        t = i / FPS
        pose = pose_for(t, phase)
        lw = (pose[15][0], pose[15][1])
        rw = (pose[16][0], pose[16][1])
        frames.append({
            "pose": pose,
            "left_hand": hand_for(lw, t, side=1),
            "right_hand": hand_for(rw, t, side=-1),
            "face": face_for(),
        })
    return {"version": "1.0", "fps": FPS, "frame_count": n, "frames": frames}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate synthetic keypoints")
    parser.add_argument("--out", default=str(KEYPOINT_DIR / "demo.json"))
    parser.add_argument("--seconds", type=float, default=FRAMES / FPS)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(args.seconds)), encoding="utf-8")
    print(f"wrote {out} ({FRAMES} frames @ {FPS}fps)")


if __name__ == "__main__":
    main()
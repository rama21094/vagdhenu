#!/usr/bin/env python3
"""Create RMS-matched final/raw/Vocos files for fair artifact comparison."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf


def normalize(audio: np.ndarray, target_dbfs: float, peak_dbfs: float) -> np.ndarray:
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    if rms == 0:
        return audio
    gain = (10 ** (target_dbfs / 20)) / rms
    peak_limit = 10 ** (peak_dbfs / 20)
    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        gain = min(gain, peak_limit / peak)
    return audio * gain


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--candidate", action="append", required=True)
    parser.add_argument("--target-dbfs", type=float, default=-20.0)
    parser.add_argument("--peak-dbfs", type=float, default=-1.0)
    args = parser.parse_args()

    variants = {
        "final": ("", ""),
        "raw_bigvgan": ("_raw", "_raw"),
        "vocos": ("_vocos", "_vocos"),
    }
    count = 0
    for candidate in args.candidate:
        for variant, (directory_suffix, filename_suffix) in variants.items():
            source_dir = args.source / f"{candidate}{directory_suffix}"
            output_dir = args.destination / candidate / variant
            output_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted(source_dir.glob("*.wav")):
                audio, sample_rate = sf.read(path, dtype="float32")
                audio = normalize(audio, args.target_dbfs, args.peak_dbfs)
                stem = path.stem.removesuffix(filename_suffix)
                sf.write(output_dir / f"{stem}.wav", audio, sample_rate, subtype="PCM_16")
                count += 1
    print(f"wrote {count} loudness-matched files to {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

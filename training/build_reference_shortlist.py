#!/usr/bin/env python3
"""Build a meter-specific source-audio shortlist for human reference selection."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--meter", required=True, help="meter substring in line_scans_json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline-id", action="append", default=[])
    parser.add_argument("--force-id", action="append", default=[])
    args = parser.parse_args()

    with args.metadata.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["clip_id"]: row for row in rows}
    eligible = [
        row for row in rows
        if row["split"] == "train"
        and args.meter in row["line_scans_json"]
        and not row["analysis_issues"]
    ]
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in eligible:
        grouped[int(row["dasakam"])].append(row)

    picks = []
    forced_by_dasakam = {int(by_id[clip_id]["dasakam"]): by_id[clip_id] for clip_id in args.force_id}
    for dasakam, candidates in sorted(grouped.items()):
        if dasakam in forced_by_dasakam:
            picks.append(forced_by_dasakam[dasakam])
            continue
        median_duration = statistics.median(float(row["duration_s"]) for row in candidates)
        picks.append(min(candidates, key=lambda row: abs(float(row["duration_s"]) - median_duration)))

    selected = [by_id[clip_id] for clip_id in args.baseline_id] + picks
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, row in enumerate(selected, start=1):
        label = f"R{index:02d}"
        destination = args.out / f"{label}.wav"
        audio, sample_rate = sf.read(row["audio_path"], dtype="float32", always_2d=True)
        mono = np.mean(audio, axis=1)
        sf.write(destination, mono, sample_rate, subtype="PCM_16")
        manifest.append(
            {
                "label": label,
                "clip_id": row["clip_id"],
                "dasakam": int(row["dasakam"]),
                "duration_s": float(row["duration_s"]),
                "text": row["text_clean"],
                "wav": destination.name,
            }
        )

    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Vasantatilakā reference shortlist",
        "",
        "These are original target-speaker recordings, not generated audio. Listen for the",
        "standard tune you want the model to reproduce. First judge tune and cadence; then",
        "prefer a clean recording with stable voice and no background noise.",
        "",
        "Record a first choice and two alternatives. The clip IDs are intentionally kept in",
        "the table because these are source references rather than model candidates.",
        "",
        "| Label | Clip | Duration | Standard tune? | Recording quality | Notes |",
        "|---|---|---:|---:|---:|---|",
    ]
    for item in manifest:
        lines.append(
            f"| {item['label']} | `{item['clip_id']}` | {item['duration_s']:.2f}s | | | |"
        )
    lines += ["", "## Texts", ""]
    for item in manifest:
        lines += [f"### {item['label']} — `{item['clip_id']}`", "", item["text"], ""]
    (args.out / "LISTENING_GUIDE.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(manifest)} references to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

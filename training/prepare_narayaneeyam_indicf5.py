#!/usr/bin/env python3
"""Create IndicF5 ``CustomDatasetPath`` datasets from enriched metadata.

Outputs two training arms:

* ``all`` keeps every structurally paired training clip.
* ``high_bandwidth`` excludes source audio below 24 kHz for an ablation.

Validation and test sets are emitted independently and are never included in
either training arm. Source FLAC files remain untouched; IndicF5 downmixes and
resamples them while loading.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def write_dataset(rows: list[dict], destination: Path, vocab: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "audio_path": row["audio_path"],
            "text": row["text_model_kannada"],
            "duration": float(row["duration_s"]),
        }
        for row in rows
    ]
    # CustomDatasetPath first tries <dir>/raw, then falls back to raw.arrow.
    from datasets.arrow_writer import ArrowWriter

    # Match IndicF5's own prepare_csv_wavs.py. Larger writer batches can leave a
    # short final batch absent with some datasets/pyarrow version combinations.
    with ArrowWriter(path=str(destination / "raw.arrow"), writer_batch_size=1) as writer:
        for record in records:
            writer.write(record)
    durations = [record["duration"] for record in records]
    (destination / "duration.json").write_text(
        json.dumps({"duration": durations}, ensure_ascii=False), encoding="utf-8"
    )
    if vocab.exists():
        shutil.copy2(vocab, destination / "vocab.txt")
    fields = [
        "clip_id", "dasakam", "verse", "half", "split", "audio_path",
        "text_devanagari", "text_clean", "text_model_kannada", "slp1",
        "duration_s", "sample_rate", "channels", "bit_depth", "analysis_issues",
    ]
    with (destination / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    summary = {
        "clips": len(records),
        "hours": sum(durations) / 3600,
        "sample_rates": dict(sorted(Counter(row["sample_rate"] for row in rows).items())),
        "dasakams": sorted({int(row["dasakam"]) for row in rows}),
    }
    (destination / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def validate_arrow(destination: Path) -> None:
    from datasets import Dataset as HFDataset

    dataset = HFDataset.from_file(str(destination / "raw.arrow"))
    durations = json.loads((destination / "duration.json").read_text(encoding="utf-8"))["duration"]
    if len(dataset) != len(durations):
        raise ValueError(f"row/duration mismatch in {destination}: {len(dataset)} != {len(durations)}")
    for index in (0, len(dataset) // 2, len(dataset) - 1):
        if index < 0:
            continue
        row = dataset[index]
        if not Path(row["audio_path"]).is_file():
            raise FileNotFoundError(row["audio_path"])
        if not row["text"].strip():
            raise ValueError(f"empty model text at row {index} in {destination}")
        if abs(float(row["duration"]) - float(durations[index])) > 1e-6:
            raise ValueError(f"duration order mismatch at row {index} in {destination}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path, help="metadata_enriched.csv")
    parser.add_argument("--out", type=Path, default=Path("data/narayaneeyam_indicf5"))
    parser.add_argument("--vocab", type=Path, default=REPO / "src/reference_bank/vocab.txt")
    args = parser.parse_args()
    with args.metadata.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    splits = {name: [row for row in rows if row["split"] == name] for name in ("train", "validation", "test")}
    train_rows = splits["train"]
    smoke_count = min(64, len(train_rows))
    smoke_indices = [round(i * (len(train_rows) - 1) / max(1, smoke_count - 1)) for i in range(smoke_count)]
    variants = {
        "all/train": splits["train"],
        "high_bandwidth/train": [row for row in splits["train"] if int(row["sample_rate"]) >= 24_000],
        "smoke/train": [train_rows[index] for index in smoke_indices],
        "validation": splits["validation"],
        "test": splits["test"],
    }
    summaries = {}
    for name, selected in variants.items():
        destination = args.out.resolve() / name
        summaries[name] = write_dataset(selected, destination, args.vocab.resolve())
        validate_arrow(destination)
        print(f"{name}: {summaries[name]['clips']} clips, {summaries[name]['hours']:.3f} h")
    (args.out.resolve() / "SUMMARY.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

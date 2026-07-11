#!/usr/bin/env python3
"""Generate the bundled quarter-level Narayaneeyam recording manifest."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from training.build_eval_shard import inferred_meter, split_quarter_padas


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source = root / "data/narayaneeyam_audit/metadata_enriched.csv"
    destination = root / "recorder/defaults/narayaneeyam.json"
    with source.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    items = []
    reviewed = 0
    for row in rows:
        try:
            quarters = split_quarter_padas(row)
            exact = True
        except ValueError:
            quarters = split_quarter_padas(row, strict=False)
            exact = False
            reviewed += 1
        scans = json.loads(row["line_scans_json"])
        for offset, text in enumerate(quarters):
            quarter = (int(row["half"]) - 1) * 2 + offset + 1
            scan = scans[offset] if offset < len(scans) else {}
            items.append(
                {
                    "id": f"{row['clip_id']}_q{offset + 1}",
                    "project": "narayaneeyam",
                    "collection": "Narayaneeyam",
                    "dasakam": int(row["dasakam"]),
                    "verse": int(row["verse"]),
                    "half": int(row["half"]),
                    "quarter": quarter,
                    "text": text.strip(),
                    "meter": inferred_meter(row),
                    "syllables": int(scan.get("syllables", 0)),
                    "weights": scan.get("weights", ""),
                    "split_exact": exact,
                    "source_clip_id": row["clip_id"],
                    "source_audio": row["audio_path"],
                }
            )

    payload = {
        "id": "narayaneeyam",
        "name": "Narayaneeyam",
        "description": "Quarter-level recording script derived from 60 Dasakams.",
        "language": "sa-Deva",
        "items": items,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} quarters to {destination}; manual split review={reviewed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


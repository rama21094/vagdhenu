#!/usr/bin/env python3
"""Build a render.py shard using an exact new-speaker reference from metadata."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


METER_SLUGS = {
    "vasantatilakā": "vasantatilakā",
    "śārdūlavikrīḍita": "śārdūlavikrīḍita",
    "upendravajrā": "upendravajrā",
    "indravajrā": "indravajrā",
    "vaṃśastha": "vaṃśastha",
    "sragdharā": "sragdharā",
    "mālinī": "mālinī",
    "śikhariṇī": "śikhariṇī",
    "pṛthvī": "vrutta-1",
    "mandākrāntā": "śārdūlavikrīḍita",
}

SLP_VOWELS = frozenset("aAiIuUfFxXeEoO")


def split_quarter_padas(row: dict) -> list[str]:
    """Split a two-quarter recording at its metrically determined word boundary."""
    scans = json.loads(row["line_scans_json"])
    if len(scans) != 2:
        raise ValueError(f"{row['clip_id']}: expected two quarter scans, got {len(scans)}")
    desired = int(scans[0]["syllables"])
    text_words = row["text_clean"].split()
    terminal = [word for word in text_words if word in {"।", "॥"}]
    text_words = [word for word in text_words if word not in {"।", "॥"}]
    slp_words = row["slp1"].split()
    if len(text_words) != len(slp_words):
        raise ValueError(
            f"{row['clip_id']}: text/SLP word mismatch {len(text_words)} != {len(slp_words)}"
        )
    cumulative = 0
    boundary = None
    for index, slp_word in enumerate(slp_words, start=1):
        cumulative += sum(character in SLP_VOWELS for character in slp_word)
        if cumulative == desired:
            boundary = index
            break
        if cumulative > desired:
            break
    if boundary is None or boundary == len(text_words):
        raise ValueError(f"{row['clip_id']}: no internal word boundary at syllable {desired}")
    first = " ".join(text_words[:boundary])
    second = " ".join(text_words[boundary:] + terminal)
    return [first, second]


def inferred_meter(row: dict) -> str:
    scans = json.loads(row["line_scans_json"])
    names = [scan["meter"].split("(", 1)[0] for scan in scans]
    if names and all(name == names[0] for name in names):
        if names[0]:
            return METER_SLUGS.get(names[0], "anuṣṭubh")
        syllables = {int(scan["syllables"]) for scan in scans}
        if syllables == {17}:
            return "vrutta-1"
    return "anuṣṭubh"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--ref-id", required=True)
    parser.add_argument("--target-id", action="append", required=True)
    parser.add_argument(
        "--case", action="append", default=[], metavar="REF_ID:TARGET_ID[:SPS]",
        help="additional case with its own exact reference and optional seconds-per-syllable",
    )
    parser.add_argument(
        "--sps", type=float, default=None,
        help="seconds per syllable for the primary --ref-id/--target-id cases",
    )
    parser.add_argument(
        "--split-padas", action="store_true",
        help="split each two-quarter target at its exact metrical word boundary",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=60)
    args = parser.parse_args()
    with args.metadata.open(encoding="utf-8") as handle:
        by_id = {row["clip_id"]: row for row in csv.DictReader(handle)}
    cases = [(args.ref_id, target_id, args.sps) for target_id in args.target_id]
    for case in args.case:
        fields = case.split(":")
        if len(fields) not in (2, 3):
            parser.error(f"invalid --case {case!r}; expected REF_ID:TARGET_ID[:SPS]")
        ref_id, target_id = fields[:2]
        sps = float(fields[2]) if len(fields) == 3 else None
        cases.append((ref_id, target_id, sps))
    shard = []
    for ref_id, target_id, sps in cases:
        ref = by_id[ref_id]
        target = by_id[target_id]
        padas = split_quarter_padas(target) if args.split_padas else [target["text_clean"]]
        item = {
                "id": f"eval_{target_id}",
                "meter": inferred_meter(target),
                "padas": padas,
                "seed": args.seed,
                "no_sandhi": True,
                "ref_wav": ref["audio_path"],
                "ref_text": ref["text_model_kannada"],
                "out": f"eval_{target_id}.wav",
                "no_autoprime": True,
            }
        if sps is not None:
            item["sps"] = sps
        shard.append(item)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(shard, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(shard)} items to {args.out}; references={sorted(set(r for r, _, _ in cases))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

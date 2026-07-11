#!/usr/bin/env python3
"""Build a render.py shard using an exact new-speaker reference from metadata."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
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

def count_aksharas(text: str) -> int:
    count = 0
    for index, character in enumerate(text):
        codepoint = ord(character)
        independent_vowel = 0x0905 <= codepoint <= 0x0914
        consonant = 0x0915 <= codepoint <= 0x0939
        if independent_vowel:
            count += 1
        elif consonant:
            following = text[index + 1] if index + 1 < len(text) else ""
            if following != "्":
                count += 1
    return count


def split_quarter_padas(row: dict, *, strict: bool = True) -> list[str]:
    """Split a two-quarter recording at its metrically determined word boundary."""
    scans = json.loads(row["line_scans_json"])
    if len(scans) != 2:
        raise ValueError(f"{row['clip_id']}: expected two quarter scans, got {len(scans)}")
    desired = int(scans[0]["syllables"])
    clean_text = re.sub(r"\s*[-–—]?\s*\([^)]*\)", " ", row["text_clean"])
    all_words = clean_text.split()
    is_lexical = lambda word: any(unicodedata.category(ch)[0] in {"L", "M"} for ch in word)
    text_words = [word for word in all_words if is_lexical(word)]
    terminal = [word for word in all_words if not is_lexical(word)]
    cumulative = 0
    boundary = None
    candidates = []
    for index, text_word in enumerate(text_words, start=1):
        cumulative += count_aksharas(text_word)
        if index < len(text_words):
            candidates.append((abs(cumulative - desired), index))
        if cumulative == desired:
            boundary = index
            break
        if cumulative > desired:
            break
    if boundary is None or boundary == len(text_words):
        if strict or not candidates:
            raise ValueError(f"{row['clip_id']}: no internal word boundary at syllable {desired}")
        boundary = min(candidates)[1]
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

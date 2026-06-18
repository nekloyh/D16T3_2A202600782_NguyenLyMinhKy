from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


DIFFICULTIES = {"easy", "medium", "hard"}


def context_to_chunks(raw_context: list[Any]) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for item in raw_context:
        if not isinstance(item, list) or len(item) != 2:
            continue

        title, sentences = item
        if isinstance(sentences, list):
            text = " ".join(str(sentence).strip() for sentence in sentences).strip()
        else:
            text = str(sentences).strip()

        chunks.append({"title": str(title), "text": text})
    return chunks


def convert_record(record: dict[str, Any]) -> dict[str, Any]:
    difficulty = str(record.get("level", "medium")).lower()
    if difficulty not in DIFFICULTIES:
        difficulty = "medium"

    return {
        "qid": str(record["_id"]),
        "difficulty": difficulty,
        "question": str(record["question"]),
        "gold_answer": str(record["answer"]),
        "context": context_to_chunks(record.get("context", [])),
    }


def create_sample(input_path: Path, output_path: Path, sample_size: int, seed: int) -> None:
    records = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"Expected a JSON list in {input_path}")
    if sample_size > len(records):
        raise ValueError(f"Requested {sample_size} records, but only found {len(records)}")

    rng = random.Random(seed)
    sampled = rng.sample(records, sample_size)
    converted = [convert_record(record) for record in sampled]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(converted, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a deterministic QAExample sample from HotpotQA JSON."
    )
    parser.add_argument("--input", default="hotpotqa.json", help="Path to source HotpotQA JSON")
    parser.add_argument(
        "--output",
        default="data/hotpot_sample_100_seed42.json",
        help="Path to write the converted sample",
    )
    parser.add_argument("--sample-size", type=int, default=100, help="Number of examples")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    create_sample(
        input_path=Path(args.input),
        output_path=Path(args.output),
        sample_size=args.sample_size,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()

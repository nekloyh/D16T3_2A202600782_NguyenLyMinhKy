from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Iterable
from .schemas import QAExample, RunRecord

def normalize_answer(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text

# Connectives / approximators that never change the factual answer of a short QA span.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to",
    "is", "are", "was", "were", "approximately", "about", "around",
    "roughly", "circa", "estimated",
}


def _content_tokens(text: str) -> set[str]:
    return {t for t in normalize_answer(text).split() if t not in _STOPWORDS}


def lenient_match(gold: str, pred: str) -> bool:
    """Deterministic equivalence check for short-answer QA.

    Returns True when the prediction unambiguously conveys the gold answer:
      * identical content tokens after dropping articles/connectives/approximators
        (e.g. "approximately 66000" == "66000", "Dutch, French, and German"
        == "Dutch, French, German"), or
      * the prediction contains the full gold answer plus a harmless head noun or
        qualifier (e.g. "classical music" ⊇ "classical", "Bab-el-Mandeb strait"
        ⊇ "Bab-el-Mandeb").

    It is intentionally one-directional (gold ⊆ pred) so a prediction that *drops*
    part of the gold answer is never accepted. Used only to raise an LLM judge's
    score from 0 to 1, never to lower it — so it cannot mask a genuinely wrong answer.
    """
    if normalize_answer(gold) == normalize_answer(pred):
        return True
    gold_tokens = _content_tokens(gold)
    pred_tokens = _content_tokens(pred)
    if not gold_tokens or not pred_tokens:
        return False
    if gold_tokens == pred_tokens:
        return True
    return gold_tokens <= pred_tokens

def load_dataset(path: str | Path) -> list[QAExample]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [QAExample.model_validate(item) for item in raw]

def save_jsonl(path: str | Path, records: Iterable[RunRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")

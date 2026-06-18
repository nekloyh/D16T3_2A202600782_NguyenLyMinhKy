from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .runtime_base import RuntimeCall
from .schemas import JudgeResult, QAExample, ReflectionEntry
from .utils import lenient_match, normalize_answer


DEFAULT_MODEL = "gpt-4o-mini"


def format_context(example: QAExample) -> str:
    return "\n\n".join(
        f"[{idx}] {chunk.title}\n{chunk.text}"
        for idx, chunk in enumerate(example.context, start=1)
    )


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Response did not contain a JSON object: {text[:300]}")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Parsed JSON was not an object")
    return value


def response_token_count(response: Any) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0
    for attr in ("total_tokens", "total"):
        value = getattr(usage, attr, None)
        if isinstance(value, int):
            return value
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    return int(input_tokens + output_tokens)


class OpenAIRuntime:
    failure_mode_by_qid: dict[str, str] = {}

    def __init__(self, model: str | None = None) -> None:
        load_dotenv()
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'openai'. Run: pip install -r requirements.txt"
            ) from exc

        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    def _response_text(self, system_prompt: str, user_prompt: str) -> RuntimeCall[str]:
        started = time.perf_counter()
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        return RuntimeCall(
            value=response.output_text.strip(),
            token_count=response_token_count(response),
            latency_ms=latency_ms,
        )

    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> RuntimeCall[str]:
        reflections = "\n".join(f"- {item}" for item in reflection_memory) or "None"
        user_prompt = f"""Question:
{example.question}

Context:
{format_context(example)}

Attempt: {attempt_id}
Agent type: {agent_type}
Reflection notes:
{reflections}

Final short answer:"""
        return self._response_text(ACTOR_SYSTEM, user_prompt)

    def evaluator(self, example: QAExample, answer: str) -> RuntimeCall[JudgeResult]:
        user_prompt = f"""Question:
{example.question}

Gold answer:
{example.gold_answer}

Predicted answer:
{answer}

Context:
{format_context(example)}

JSON evaluation:"""
        call = self._response_text(EVALUATOR_SYSTEM, user_prompt)
        try:
            judge = JudgeResult.model_validate(extract_json_object(call.value))
        except (ValueError, json.JSONDecodeError, ValidationError):
            score = int(normalize_answer(example.gold_answer) == normalize_answer(answer))
            judge = JudgeResult(
                score=score,
                reason="Evaluator JSON parsing failed; fell back to exact-match normalization.",
                missing_evidence=[] if score else ["Evaluator did not return parseable JSON."],
                spurious_claims=[] if score else [answer],
            )

        # Deterministic safety net: if the prediction lexically contains the full
        # gold answer (modulo articles/qualifiers), force a correct verdict so a
        # strict-mood judge cannot reject e.g. "classical music" vs gold "classical".
        # This only ever raises 0 -> 1, never lowers a score.
        if judge.score == 0 and lenient_match(example.gold_answer, answer):
            judge = judge.model_copy(
                update={
                    "score": 1,
                    "reason": (
                        "Lenient match: prediction conveys the gold answer "
                        "(extra wording is a harmless qualifier)."
                    ),
                    "spurious_claims": [],
                }
            )
        return RuntimeCall(value=judge, token_count=call.token_count, latency_ms=call.latency_ms)

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        answer: str,
        judge: JudgeResult,
    ) -> RuntimeCall[ReflectionEntry]:
        user_prompt = f"""Question:
{example.question}

Context:
{format_context(example)}

Wrong answer:
{answer}

Evaluator feedback:
{judge.model_dump_json()}

Reflection JSON:"""
        call = self._response_text(REFLECTOR_SYSTEM, user_prompt)
        try:
            payload = extract_json_object(call.value)
            reflection = ReflectionEntry(
                attempt_id=attempt_id,
                failure_reason=str(payload["failure_reason"]),
                lesson=str(payload["lesson"]),
                next_strategy=str(payload["next_strategy"]),
            )
        except (KeyError, ValueError, json.JSONDecodeError):
            reflection = ReflectionEntry(
                attempt_id=attempt_id,
                failure_reason=judge.reason,
                lesson="Use the context more carefully before committing to a final answer.",
                next_strategy="Re-read the supporting context and verify each reasoning hop.",
            )
        return RuntimeCall(
            value=reflection,
            token_count=call.token_count,
            latency_ms=call.latency_ms,
        )

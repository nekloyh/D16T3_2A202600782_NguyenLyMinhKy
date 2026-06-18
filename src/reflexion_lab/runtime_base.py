from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from .schemas import JudgeResult, QAExample, ReflectionEntry


T = TypeVar("T")


@dataclass(frozen=True)
class RuntimeCall(Generic[T]):
    value: T
    token_count: int = 0
    latency_ms: int = 0


class AgentRuntime(Protocol):
    failure_mode_by_qid: dict[str, str]

    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> RuntimeCall[str]:
        ...

    def evaluator(self, example: QAExample, answer: str) -> RuntimeCall[JudgeResult]:
        ...

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        answer: str,
        judge: JudgeResult,
    ) -> RuntimeCall[ReflectionEntry]:
        ...

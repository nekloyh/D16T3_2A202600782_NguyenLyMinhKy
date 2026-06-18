from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .mock_runtime import MockRuntime
from .runtime_base import AgentRuntime
from .schemas import AttemptTrace, QAExample, ReflectionEntry, RunRecord
from .utils import normalize_answer

INCOMPLETE_SIGNALS = (
    "does not provide", "not provide", "not enough", "cannot determine",
    "no information", "unable to", "insufficient", "not specified", "not mentioned",
)


def classify_failure_mode(gold_answer: str, traces: list[AttemptTrace], agent_type: str) -> str:
    """Heuristic error analysis from the trajectory (not from the EM score).

    Categorises *why* a wrong record failed using only the attempt answers and the
    gold answer for typing — it never alters correctness, so it cannot inflate EM.
    """
    answers = [t.answer for t in traces]
    if not answers:
        return "wrong_final_answer"
    norm_answers = [normalize_answer(a) for a in answers]
    gold_tokens = set(normalize_answer(gold_answer).split())
    final_tokens = set(norm_answers[-1].split())

    # 1. Agent admitted missing evidence, or final answer is a strict subset of gold (a hop dropped).
    if any(any(s in a.lower() for s in INCOMPLETE_SIGNALS) for a in answers):
        return "incomplete_multi_hop"
    if gold_tokens and final_tokens and final_tokens < gold_tokens:
        return "incomplete_multi_hop"

    # 2. Reflection ballooned a short answer into a full sentence (made it worse).
    if agent_type == "reflexion" and len(answers) >= 2:
        if len(norm_answers[-1].split()) >= 6 and len(norm_answers[-1].split()) > len(norm_answers[0].split()):
            return "reflection_overfit"

    # 3. Same answer repeated across attempts — agent stuck in a loop.
    if len(norm_answers) >= 2 and len(set(norm_answers)) < len(norm_answers):
        return "looping"

    # 4. A different short entity than gold, with no token overlap — wrong-entity drift.
    if final_tokens and gold_tokens and len(final_tokens) <= 6 and len(gold_tokens) <= 6 \
            and not (final_tokens & gold_tokens):
        return "entity_drift"

    # 5. Fallback.
    return "wrong_final_answer"


@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1
    runtime: AgentRuntime | None = None

    def run(self, example: QAExample) -> RunRecord:
        runtime = self.runtime or MockRuntime()
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = -1
        seen_answers: list[str] = []
        for attempt_id in range(1, self.max_attempts + 1):
            answer_call = runtime.actor_answer(example, attempt_id, self.agent_type, reflection_memory)
            answer = answer_call.value
            judge_call = runtime.evaluator(example, answer)
            judge = judge_call.value
            token_estimate = answer_call.token_count + judge_call.token_count
            latency_ms = answer_call.latency_ms + judge_call.latency_ms
            trace = AttemptTrace(
                attempt_id=attempt_id,
                answer=answer,
                score=judge.score,
                reason=judge.reason,
                token_estimate=token_estimate,
                latency_ms=latency_ms,
            )
            # Keep the best answer across attempts; among ties keep the earliest
            # so a later reflection drift cannot overwrite a cleaner early answer.
            if judge.score > final_score:
                final_answer = answer
                final_score = judge.score
            if judge.score == 1:
                traces.append(trace)
                break
            # Early stop: the actor is repeating a wrong answer, so further
            # reflection only burns tokens without changing the outcome.
            normalized = normalize_answer(answer)
            if normalized in seen_answers:
                traces.append(trace)
                break
            seen_answers.append(normalized)
            if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                reflection_call = runtime.reflector(example, attempt_id, answer, judge)
                reflection = reflection_call.value
                reflections.append(reflection)
                reflection_memory.append(reflection.next_strategy)
                trace.reflection = reflection
                trace.token_estimate += reflection_call.token_count
                trace.latency_ms += reflection_call.latency_ms
            traces.append(trace)
        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        failure_mode = "none" if final_score == 1 else classify_failure_mode(example.gold_answer, traces, self.agent_type)
        return RunRecord(qid=example.qid, question=example.question, gold_answer=example.gold_answer, agent_type=self.agent_type, predicted_answer=final_answer, is_correct=bool(final_score), attempts=len(traces), token_estimate=total_tokens, latency_ms=total_latency, failure_mode=failure_mode, reflections=reflections, traces=traces)

class ReActAgent(BaseAgent):
    def __init__(self, runtime: AgentRuntime | None = None) -> None:
        super().__init__(agent_type="react", max_attempts=1, runtime=runtime)

class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3, runtime: AgentRuntime | None = None) -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts, runtime=runtime)

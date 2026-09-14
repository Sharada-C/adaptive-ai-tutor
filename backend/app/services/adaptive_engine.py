from dataclasses import dataclass


@dataclass
class AdaptiveDecision:
    action: str
    reason: str
    mastery_score: float
    prerequisite_concept_id: int | None = None
    prerequisite_concept: str | None = None
    prerequisite_mastery_score: float | None = None


ADVANCE_THRESHOLD = 0.80
PRACTICE_THRESHOLD = 0.50


def decide_next_action(
    mastery_score: float,
    has_active_misconception: bool = False,
    prerequisites_mastered: bool = True,
    weakest_prerequisite: dict | None = None,
) -> AdaptiveDecision:

    # 1. Highest priority: fix misconception.
    if has_active_misconception:
        return AdaptiveDecision(
            action="reteach",
            reason="Student has an active misconception.",
            mastery_score=mastery_score,
        )

    # 2. Current concept is mastered, but prerequisite is weak.
    if mastery_score >= ADVANCE_THRESHOLD and not prerequisites_mastered:

        if weakest_prerequisite:
            return AdaptiveDecision(
                action="prerequisite",
                reason=(
                    f"Prerequisite "
                    f"'{weakest_prerequisite['concept']}' "
                    f"has insufficient mastery."
                ),
                mastery_score=mastery_score,
                prerequisite_concept_id=(
                    weakest_prerequisite["concept_id"]
                ),
                prerequisite_concept=(
                    weakest_prerequisite["concept"]
                ),
                prerequisite_mastery_score=(
                    weakest_prerequisite["mastery_score"]
                ),
            )

        return AdaptiveDecision(
            action="prerequisite",
            reason=(
                "Current concept is mastered, but a prerequisite "
                "concept has insufficient mastery."
            ),
            mastery_score=mastery_score,
        )

    # 3. Current concept mastered and prerequisites satisfied.
    if mastery_score >= ADVANCE_THRESHOLD:
        return AdaptiveDecision(
            action="advance",
            reason="Student has demonstrated sufficient mastery.",
            mastery_score=mastery_score,
        )

    # 4. Partial understanding.
    if mastery_score >= PRACTICE_THRESHOLD:
        return AdaptiveDecision(
            action="practice",
            reason=(
                "Student has partial understanding "
                "and needs more practice."
            ),
            mastery_score=mastery_score,
        )

    # 5. Low mastery.
    return AdaptiveDecision(
        action="reteach",
        reason="Student mastery is below the practice threshold.",
        mastery_score=mastery_score,
    )
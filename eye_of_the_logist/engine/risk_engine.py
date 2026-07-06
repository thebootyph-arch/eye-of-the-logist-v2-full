"""
Risk Engine — считает итоговый Score от 0 до 100.
Decision Engine — выносит вердикт.
"""
from audit.base_rule import AuditResult, Status, Severity, SEVERITY_SCORE
from state.pipeline_state import PipelineState


SCORE_START = 100

THRESHOLDS = {
    "APPROVED":     (90, 100),
    "CONDITIONAL":  (70, 89),
    "REJECTED":     (0,  69),
}


class RiskEngine:
    def calculate(self, state: PipelineState) -> int:
        score = SCORE_START
        for result in state.audit_results:
            if result.status == Status.FAIL:
                score += result.score_impact  # score_impact отрицательный
        state.risk_score = max(0, min(100, score))
        return state.risk_score

    def summary(self, state: PipelineState) -> dict:
        fails     = [r for r in state.audit_results if r.status == Status.FAIL]
        passes    = [r for r in state.audit_results if r.status == Status.PASS]
        skips     = [r for r in state.audit_results if r.status == Status.SKIP]
        deducted  = sum(abs(r.score_impact) for r in fails)
        by_severity = {}
        for sev in Severity:
            count = sum(1 for r in fails if r.severity == sev)
            if count:
                by_severity[sev.value] = count
        return {
            "score":          state.risk_score,
            "start":          SCORE_START,
            "deducted":       deducted,
            "total_rules":    len(state.audit_results),
            "passed":         len(passes),
            "failed":         len(fails),
            "skipped":        len(skips),
            "by_severity":    by_severity,
        }


class DecisionEngine:
    def decide(self, state: PipelineState) -> str:
        score = state.risk_score
        if score >= 90:
            state.decision = "APPROVED"
        elif score >= 70:
            state.decision = "CONDITIONAL_APPROVAL"
        else:
            state.decision = "REJECTED"

        # Собираем причины отказа / условия
        failed = [r for r in state.audit_results if r.status == Status.FAIL]
        state.rejection_reasons = [r.message for r in failed]
        return state.decision

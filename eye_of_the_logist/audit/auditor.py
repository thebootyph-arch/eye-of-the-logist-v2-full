"""
Cross Document Auditor — запускает группы правил в правильном порядке.
F → A → B → C → D → E
Если Group F даёт CRITICAL FAIL — дальше не идём.
"""
from audit.base_rule import Status, Severity
from audit.groups.group_f import GROUP_F_RULES
from audit.groups.group_a import GROUP_A_RULES
from audit.groups.group_bcde import (
    GROUP_B_RULES, GROUP_C_RULES, GROUP_D_RULES, GROUP_E_RULES
)
from state.pipeline_state import PipelineState


class CrossDocumentAuditor:
    def run(self, state: PipelineState) -> None:
        # ── Group F: Document Completeness (обязательная, блокирующая) ──
        for rule in GROUP_F_RULES:
            result = rule.check(state)
            state.audit_results.append(result)

        # Если есть CRITICAL в F — дальше не идём
        critical_f_fails = [
            r for r in state.audit_results
            if r.status == Status.FAIL and r.severity == Severity.CRITICAL
        ]
        if critical_f_fails:
            state.add_error(
                f"Pipeline halted after Group F: "
                f"{len(critical_f_fails)} critical document(s) missing."
            )
            return

        # ── Groups A–E: основной аудит ───────────────────────────────
        for rule in GROUP_A_RULES:
            state.audit_results.append(rule.check(state))

        for rule in GROUP_B_RULES:
            state.audit_results.append(rule.check(state))

        for rule in GROUP_C_RULES:
            state.audit_results.append(rule.check(state))

        for rule in GROUP_D_RULES:
            state.audit_results.append(rule.check(state))

        for rule in GROUP_E_RULES:
            state.audit_results.append(rule.check(state))

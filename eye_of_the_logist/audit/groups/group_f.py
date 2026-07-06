"""
Group F — Document Completeness
Выполняется ПЕРВОЙ. Если хотя бы один CRITICAL FAIL — дальше не идём.
"""
from audit.base_rule import BaseRule, AuditResult, Severity, Status
from state.pipeline_state import PipelineState

GROUP = "F"
MIN_CONFIDENCE = 0.70


class F001_CMR_Present(BaseRule):
    rule_id   = "F001"
    rule_name = "CMR Present"
    group     = GROUP

    def check(self, state: PipelineState) -> AuditResult:
        if state.has_cmr():
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      "CMR document received.", ["CMR"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.CRITICAL,
                                  "CMR is missing. Cannot process shipment without transport document.",
                                  ["CMR"])


class F002_Invoice_Present(BaseRule):
    rule_id   = "F002"
    rule_name = "Invoice Present"
    group     = GROUP

    def check(self, state: PipelineState) -> AuditResult:
        if state.has_invoice():
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      "Commercial Invoice received.", ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.CRITICAL,
                                  "Commercial Invoice is missing. Required for customs valuation.",
                                  ["INVOICE"])


class F003_PackingList_Present(BaseRule):
    rule_id   = "F003"
    rule_name = "Packing List Present"
    group     = GROUP

    def check(self, state: PipelineState) -> AuditResult:
        if state.has_packing_list():
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      "Packing List received.", ["PACKING_LIST"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.CRITICAL,
                                  "Packing List is missing. Required for physical cargo verification.",
                                  ["PACKING_LIST"])


class F004_CMR_Not_Empty(BaseRule):
    rule_id   = "F004"
    rule_name = "CMR Fields Present"
    group     = GROUP

    REQUIRED_FIELDS = ["shipper_name", "consignee_name", "cargo_description",
                       "loading_country", "destination_country"]

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP,
                                       "Skipped: CMR not uploaded.")
        n = state.normalized
        missing = [f for f in self.REQUIRED_FIELDS if not getattr(n, f, None)]
        if not missing:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      "All mandatory CMR fields extracted.", ["CMR"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.HIGH,
                                  f"CMR is missing mandatory fields: {', '.join(missing)}",
                                  ["CMR"], detail={"missing_fields": missing})


class F005_Invoice_Not_Empty(BaseRule):
    rule_id   = "F005"
    rule_name = "Invoice Fields Present"
    group     = GROUP

    REQUIRED_FIELDS = ["seller_name", "buyer_name", "total_value",
                       "currency", "hs_code"]

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP,
                                       "Skipped: Invoice not uploaded.")
        n = state.normalized
        missing = [f for f in self.REQUIRED_FIELDS if not getattr(n, f, None)]
        if not missing:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      "All mandatory Invoice fields extracted.", ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.HIGH,
                                  f"Invoice is missing mandatory fields: {', '.join(missing)}",
                                  ["INVOICE"], detail={"missing_fields": missing})


class F006_PackingList_Not_Empty(BaseRule):
    rule_id   = "F006"
    rule_name = "Packing List Fields Present"
    group     = GROUP

    REQUIRED_FIELDS = ["packages_count", "gross_weight_kg", "volume_cbm"]

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_packing_list():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP,
                                       "Skipped: Packing List not uploaded.")
        n = state.normalized
        missing = [f for f in self.REQUIRED_FIELDS if not getattr(n, f, None)]
        if not missing:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      "All mandatory Packing List fields extracted.", ["PACKING_LIST"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.HIGH,
                                  f"Packing List is missing mandatory fields: {', '.join(missing)}",
                                  ["PACKING_LIST"], detail={"missing_fields": missing})


class F007_Confidence_Score(BaseRule):
    rule_id   = "F007"
    rule_name = "Parser Confidence Score"
    group     = GROUP

    def check(self, state: PipelineState) -> AuditResult:
        low = {}
        for doc, score in [("CMR",          state.cmr_confidence),
                            ("INVOICE",      state.invoice_confidence),
                            ("PACKING_LIST", state.packing_list_confidence)]:
            if score > 0 and score < MIN_CONFIDENCE:
                low[doc] = round(score, 2)

        if not low:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      f"All parsers confidence ≥ {MIN_CONFIDENCE}.",
                                      list(low.keys()) or ["CMR", "INVOICE", "PACKING_LIST"])
        docs_str = ", ".join(f"{d}={v}" for d, v in low.items())
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.MEDIUM,
                                  f"Low parser confidence detected: {docs_str}. "
                                  f"Results may be unreliable. Review extracted data manually.",
                                  list(low.keys()), detail={"scores": low})


# ── Registry ──────────────────────────────────────────────────────────────────
GROUP_F_RULES: list[BaseRule] = [
    F001_CMR_Present(),
    F002_Invoice_Present(),
    F003_PackingList_Present(),
    F004_CMR_Not_Empty(),
    F005_Invoice_Not_Empty(),
    F006_PackingList_Not_Empty(),
    F007_Confidence_Score(),
]

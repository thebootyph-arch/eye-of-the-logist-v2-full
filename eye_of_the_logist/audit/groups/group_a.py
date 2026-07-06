"""
Group A — Identity Consistency
Проверяет совпадение сторон сделки между документами.
Использует fuzzy matching — названия компаний могут слегка отличаться.
"""
from audit.base_rule import BaseRule, AuditResult, Severity
from state.pipeline_state import PipelineState

GROUP = "A"
FUZZY_THRESHOLD = 85  # минимальный % совпадения для fuzzy match


def _fuzzy_match(a: str, b: str) -> tuple[bool, int]:
    """
    Простой fuzzy match без внешних библиотек.
    Возвращает (совпадает, score%).
    В продакшене заменить на rapidfuzz.
    """
    if not a or not b:
        return False, 0
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return True, 100
    # Проверяем содержит ли одна строка другую
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter in longer:
        score = int(len(shorter) / len(longer) * 100)
        return score >= FUZZY_THRESHOLD, score
    # Биграммное сходство
    def bigrams(s): return {s[i:i+2] for i in range(len(s)-1)}
    bg_a, bg_b = bigrams(a), bigrams(b)
    if not bg_a or not bg_b:
        return False, 0
    score = int(2 * len(bg_a & bg_b) / (len(bg_a) + len(bg_b)) * 100)
    return score >= FUZZY_THRESHOLD, score


class A001_Shipper_Seller_Match(BaseRule):
    rule_id   = "A001"
    rule_name = "Shipper = Seller Match"
    group     = GROUP

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP,
                                       "Skipped: CMR or Invoice missing.")
        n = state.normalized
        match, score = _fuzzy_match(n.shipper_name, n.seller_name)
        if match:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      f"Shipper '{n.shipper_name}' matches Seller '{n.seller_name}' "
                                      f"(score: {score}%).",
                                      ["CMR", "INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.HIGH,
                                  f"Shipper mismatch: CMR='{n.shipper_name}' vs "
                                  f"Invoice='{n.seller_name}' (score: {score}%).",
                                  ["CMR", "INVOICE"],
                                  detail={"cmr_shipper": n.shipper_name,
                                          "invoice_seller": n.seller_name,
                                          "match_score": score})


class A002_Consignee_Buyer_Match(BaseRule):
    rule_id   = "A002"
    rule_name = "Consignee = Buyer Match"
    group     = GROUP

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP,
                                       "Skipped: CMR or Invoice missing.")
        n = state.normalized
        match, score = _fuzzy_match(n.consignee_name, n.buyer_name)
        if match:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      f"Consignee '{n.consignee_name}' matches Buyer "
                                      f"'{n.buyer_name}' (score: {score}%).",
                                      ["CMR", "INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.HIGH,
                                  f"Consignee mismatch: CMR='{n.consignee_name}' vs "
                                  f"Invoice='{n.buyer_name}' (score: {score}%).",
                                  ["CMR", "INVOICE"],
                                  detail={"cmr_consignee": n.consignee_name,
                                          "invoice_buyer": n.buyer_name,
                                          "match_score": score})


class A003_VAT_Match(BaseRule):
    rule_id   = "A003"
    rule_name = "VAT / Tax ID Match"
    group     = GROUP

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP,
                                       "Skipped: Invoice missing.")
        n = state.normalized
        # Сравниваем VAT продавца: Invoice vs Packing List
        seller_vat_inv = n.seller_vat_id.strip().upper().replace(" ", "")
        seller_vat_pl  = n.seller_vat_id.strip().upper().replace(" ", "")
        # TODO: когда PL модель будет отдельной — брать из packing_list_raw
        if not seller_vat_inv:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                      Severity.HIGH,
                                      "Seller VAT/Tax ID is missing from Invoice. "
                                      "Required for customs and VAT compliance.",
                                      ["INVOICE"])
        return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                  f"Seller VAT ID present: {seller_vat_inv}.",
                                  ["INVOICE"])


class A004_Shipper_Country_Match(BaseRule):
    rule_id   = "A004"
    rule_name = "Shipper Country = Seller Country"
    group     = GROUP

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP,
                                       "Skipped: CMR or Invoice missing.")
        n = state.normalized
        c1 = n.shipper_country.upper()
        c2 = n.seller_country.upper()
        if not c1 or not c2:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                      Severity.MEDIUM,
                                      "Cannot verify country match: one or both country fields are empty.",
                                      ["CMR", "INVOICE"])
        if c1 == c2:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      f"Shipper country matches Seller country: {c1}.",
                                      ["CMR", "INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.HIGH,
                                  f"Country mismatch: CMR Shipper='{c1}' vs Invoice Seller='{c2}'. "
                                  f"Possible third-party shipment or data error.",
                                  ["CMR", "INVOICE"],
                                  detail={"cmr_shipper_country": c1,
                                          "invoice_seller_country": c2})


class A005_Consignee_Country_Match(BaseRule):
    rule_id   = "A005"
    rule_name = "Consignee Country = Buyer Country"
    group     = GROUP

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP,
                                       "Skipped: CMR or Invoice missing.")
        n = state.normalized
        c1 = n.consignee_country.upper()
        c2 = n.buyer_country.upper()
        if not c1 or not c2:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                      Severity.MEDIUM,
                                      "Cannot verify consignee country: one or both fields are empty.",
                                      ["CMR", "INVOICE"])
        if c1 == c2:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP,
                                      f"Consignee country matches Buyer country: {c1}.",
                                      ["CMR", "INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP,
                                  Severity.HIGH,
                                  f"Country mismatch: CMR Consignee='{c1}' vs Invoice Buyer='{c2}'.",
                                  ["CMR", "INVOICE"],
                                  detail={"cmr_consignee_country": c1,
                                          "invoice_buyer_country": c2})


# ── Registry ──────────────────────────────────────────────────────────────────
GROUP_A_RULES: list[BaseRule] = [
    A001_Shipper_Seller_Match(),
    A002_Consignee_Buyer_Match(),
    A003_VAT_Match(),
    A004_Shipper_Country_Match(),
    A005_Consignee_Country_Match(),
]

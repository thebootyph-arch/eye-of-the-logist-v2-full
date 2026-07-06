"""
Groups B, C, D, E — Cargo / Commercial / Logistics / Customs
"""
from audit.base_rule import BaseRule, AuditResult, Severity
from state.pipeline_state import PipelineState

# ══════════════════════════════════════════════════════════════════
# GROUP B — CARGO CONSISTENCY
# ══════════════════════════════════════════════════════════════════
GROUP_B = "B"

# Плотности (кг/м³) по первым 2 цифрам HS кода: [min, max]
HS_DENSITY_RANGES: dict[str, tuple[float, float]] = {
    "61": (30,  300),   # Трикотажная одежда
    "62": (30,  300),   # Тканая одежда
    "72": (2000, 8000), # Сталь
    "73": (1000, 7000), # Изделия из стали
    "84": (100, 3000),  # Машины и механизмы
    "85": (50,  2000),  # Электрооборудование
    "39": (50,  1200),  # Пластмассы
    "64": (100, 600),   # Обувь
    "94": (30,  500),   # Мебель
}


def _weight_delta(w1: float, w2: float, tolerance_pct: float) -> tuple[bool, float]:
    if w1 == 0 or w2 == 0:
        return False, 0.0
    delta = abs(w1 - w2) / max(w1, w2) * 100
    return delta <= tolerance_pct, round(delta, 2)


class B001_Description_Match(BaseRule):
    rule_id   = "B001"
    rule_name = "Cargo Description Match"
    group     = GROUP_B

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_B,
                                       "Skipped: CMR or Invoice missing.")
        n = state.normalized
        # Проверяем что описание не пустое в обоих документах
        if not n.cargo_description:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP_B,
                                      Severity.MEDIUM,
                                      "Cargo description is empty — cannot verify consistency.",
                                      ["CMR", "INVOICE"])
        # Semantic match делается через Gemini в auditor.py (дорогой вызов)
        # Здесь базовая проверка — описание непустое
        return AuditResult.passed(self.rule_id, self.rule_name, GROUP_B,
                                  f"Cargo description present: '{n.cargo_description[:80]}'.",
                                  ["CMR", "INVOICE"])


class B002_HS_Code_Match(BaseRule):
    rule_id   = "B002"
    rule_name = "HS Code Match (all documents)"
    group     = GROUP_B

    def check(self, state: PipelineState) -> AuditResult:
        n = state.normalized
        hs = n.hs_code.replace(".", "").strip()
        if not hs:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP_B,
                                      Severity.HIGH,
                                      "HS Code is missing across all documents.",
                                      ["CMR", "INVOICE", "PACKING_LIST"])
        if len(hs) < 6:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP_B,
                                      Severity.HIGH,
                                      f"HS Code '{hs}' is too short (min 6 digits required).",
                                      ["INVOICE"],
                                      detail={"hs_code": hs, "length": len(hs)})
        return AuditResult.passed(self.rule_id, self.rule_name, GROUP_B,
                                  f"HS Code '{hs}' present and valid format.",
                                  ["CMR", "INVOICE", "PACKING_LIST"])


class B003_Packages_Count_Match(BaseRule):
    rule_id   = "B003"
    rule_name = "Package Count Match (CMR = PL)"
    group     = GROUP_B

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_packing_list():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_B,
                                       "Skipped: CMR or Packing List missing.")
        n = state.normalized
        cmr_count = state.cmr_raw.get("packages_count", 0)
        pl_count  = n.packages_count
        if cmr_count == pl_count:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_B,
                                      f"Package count matches: {cmr_count} packages.",
                                      ["CMR", "PACKING_LIST"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_B,
                                  Severity.CRITICAL,
                                  f"Package count mismatch: CMR={cmr_count} vs PL={pl_count}. "
                                  f"Delta: {abs(cmr_count - pl_count)} packages.",
                                  ["CMR", "PACKING_LIST"],
                                  detail={"cmr": cmr_count, "pl": pl_count})


class B004_Gross_Weight_CMR_Invoice(BaseRule):
    rule_id   = "B004"
    rule_name = "Gross Weight Match (CMR = Invoice)"
    group     = GROUP_B

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_B,
                                       "Skipped: CMR or Invoice missing.")
        n = state.normalized
        w_cmr = float(state.cmr_raw.get("gross_weight_kg", 0))
        w_inv = float(state.invoice_raw.get("gross_weight_kg", 0))
        ok, delta = _weight_delta(w_cmr, w_inv, 2.0)
        if ok:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_B,
                                      f"Weight match CMR={w_cmr}kg vs Invoice={w_inv}kg (Δ{delta}%).",
                                      ["CMR", "INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_B,
                                  Severity.CRITICAL,
                                  f"Weight mismatch: CMR={w_cmr}kg vs Invoice={w_inv}kg (Δ{delta}% > 2%).",
                                  ["CMR", "INVOICE"],
                                  detail={"cmr_kg": w_cmr, "invoice_kg": w_inv, "delta_pct": delta})


class B005_Gross_Weight_CMR_PL(BaseRule):
    rule_id   = "B005"
    rule_name = "Gross Weight Match (CMR = Packing List)"
    group     = GROUP_B

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_packing_list():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_B,
                                       "Skipped: CMR or Packing List missing.")
        n = state.normalized
        w_cmr = float(state.cmr_raw.get("gross_weight_kg", 0))
        w_pl  = n.gross_weight_kg
        ok, delta = _weight_delta(w_cmr, w_pl, 2.0)
        if ok:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_B,
                                      f"Weight match CMR={w_cmr}kg vs PL={w_pl}kg (Δ{delta}%).",
                                      ["CMR", "PACKING_LIST"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_B,
                                  Severity.CRITICAL,
                                  f"Weight mismatch: CMR={w_cmr}kg vs PL={w_pl}kg (Δ{delta}% > 2%).",
                                  ["CMR", "PACKING_LIST"],
                                  detail={"cmr_kg": w_cmr, "pl_kg": w_pl, "delta_pct": delta})


class B006_Volume_Match(BaseRule):
    rule_id   = "B006"
    rule_name = "Volume Match (CMR = PL ±5%)"
    group     = GROUP_B

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_packing_list():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_B,
                                       "Skipped: CMR or Packing List missing.")
        n = state.normalized
        v_cmr = float(state.cmr_raw.get("volume_cbm", 0))
        v_pl  = n.volume_cbm
        if v_cmr == 0 or v_pl == 0:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_B,
                                       "Skipped: volume not specified in one or both documents.")
        ok, delta = _weight_delta(v_cmr, v_pl, 5.0)
        if ok:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_B,
                                      f"Volume match CMR={v_cmr}m³ vs PL={v_pl}m³ (Δ{delta}%).",
                                      ["CMR", "PACKING_LIST"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_B,
                                  Severity.MEDIUM,
                                  f"Volume mismatch: CMR={v_cmr}m³ vs PL={v_pl}m³ (Δ{delta}% > 5%).",
                                  ["CMR", "PACKING_LIST"],
                                  detail={"cmr_cbm": v_cmr, "pl_cbm": v_pl, "delta_pct": delta})


class B007_Net_Less_Than_Gross(BaseRule):
    rule_id   = "B007"
    rule_name = "Net Weight < Gross Weight"
    group     = GROUP_B

    def check(self, state: PipelineState) -> AuditResult:
        n = state.normalized
        if n.net_weight_kg == 0 or n.gross_weight_kg == 0:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_B,
                                       "Skipped: net or gross weight not available.")
        if n.net_weight_kg < n.gross_weight_kg:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_B,
                                      f"Net={n.net_weight_kg}kg < Gross={n.gross_weight_kg}kg. Logical.",
                                      ["INVOICE", "PACKING_LIST"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_B,
                                  Severity.HIGH,
                                  f"Impossible: Net weight ({n.net_weight_kg}kg) ≥ "
                                  f"Gross weight ({n.gross_weight_kg}kg). Data error.",
                                  ["INVOICE", "PACKING_LIST"],
                                  detail={"net_kg": n.net_weight_kg, "gross_kg": n.gross_weight_kg})


GROUP_B_RULES: list[BaseRule] = [
    B001_Description_Match(), B002_HS_Code_Match(), B003_Packages_Count_Match(),
    B004_Gross_Weight_CMR_Invoice(), B005_Gross_Weight_CMR_PL(),
    B006_Volume_Match(), B007_Net_Less_Than_Gross(),
]


# ══════════════════════════════════════════════════════════════════
# GROUP C — COMMERCIAL CONSISTENCY
# ══════════════════════════════════════════════════════════════════
GROUP_C = "C"

# Минимальные цены EUR/kg по первым 2 цифрам HS
HS_PRICE_FLOOR: dict[str, float] = {
    "61": 3.0,   # Трикотажная одежда — ниже 3 EUR/kg подозрительно
    "62": 3.0,   # Тканая одежда
    "64": 5.0,   # Обувь
    "84": 2.0,   # Машины
    "85": 3.0,   # Электроника
    "39": 0.8,   # Пластик
    "72": 0.4,   # Сталь
}

VALID_INCOTERMS = {"EXW","FCA","FAS","FOB","CFR","CIF","CPT","CIP","DAP","DPU","DDP"}


class C001_Invoice_Number_In_CMR(BaseRule):
    rule_id   = "C001"
    rule_name = "Invoice Number Referenced in CMR"
    group     = GROUP_C

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: CMR or Invoice missing.")
        n = state.normalized
        inv_num = state.invoice_raw.get("document_number", "")
        docs_attached = state.cmr_raw.get("documents_attached", [])
        if inv_num and any(inv_num.lower() in d.lower() for d in docs_attached):
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_C,
                                      f"Invoice '{inv_num}' found in CMR attached documents list.",
                                      ["CMR", "INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_C,
                                  Severity.MEDIUM,
                                  f"Invoice number '{inv_num}' not referenced in CMR documents list. "
                                  f"Risk of document set mismatch.",
                                  ["CMR", "INVOICE"],
                                  detail={"invoice_number": inv_num, "cmr_docs": docs_attached})


class C002_Currency_Present(BaseRule):
    rule_id   = "C002"
    rule_name = "Currency Present"
    group     = GROUP_C

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: Invoice missing.")
        n = state.normalized
        if n.currency:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_C,
                                      f"Currency present: {n.currency}.", ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_C,
                                  Severity.HIGH,
                                  "Currency is missing from Invoice. Cannot determine customs value.",
                                  ["INVOICE"])


class C003_Incoterms_Present(BaseRule):
    rule_id   = "C003"
    rule_name = "Incoterms Present and Valid"
    group     = GROUP_C

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: Invoice missing.")
        n = state.normalized
        inc = n.incoterms.upper().strip()
        if not inc:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP_C,
                                      Severity.HIGH,
                                      "Incoterms missing from Invoice.",
                                      ["INVOICE"])
        if inc not in VALID_INCOTERMS:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP_C,
                                      Severity.MEDIUM,
                                      f"Incoterms '{inc}' is not a valid ICC 2020 term.",
                                      ["INVOICE"], detail={"found": inc})
        return AuditResult.passed(self.rule_id, self.rule_name, GROUP_C,
                                  f"Incoterms '{inc}' is valid.", ["INVOICE"])


class C004_Incoterms_Consistent(BaseRule):
    rule_id   = "C004"
    rule_name = "Incoterms Consistent (Invoice = PL)"
    group     = GROUP_C

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice() or not state.has_packing_list():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: Invoice or PL missing.")
        inc_inv = state.invoice_raw.get("shipment", {}).get("incoterms", "").upper()
        inc_pl  = state.packing_list_raw.get("shipment", {}).get("incoterms", "").upper()
        if not inc_inv or not inc_pl:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: Incoterms not found in one or both documents.")
        if inc_inv == inc_pl:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_C,
                                      f"Incoterms consistent: {inc_inv}.", ["INVOICE", "PACKING_LIST"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_C,
                                  Severity.MEDIUM,
                                  f"Incoterms mismatch: Invoice='{inc_inv}' vs PL='{inc_pl}'.",
                                  ["INVOICE", "PACKING_LIST"],
                                  detail={"invoice": inc_inv, "pl": inc_pl})


class C005_Unit_Price_Valid(BaseRule):
    rule_id   = "C005"
    rule_name = "Unit Price > 0"
    group     = GROUP_C

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: Invoice missing.")
        n = state.normalized
        if n.total_value > 0:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_C,
                                      f"Total invoice value: {n.total_value} {n.currency}.",
                                      ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_C,
                                  Severity.HIGH,
                                  "Invoice total value is 0 or missing. "
                                  "Cannot determine customs dutiable value.",
                                  ["INVOICE"])


class C006_Total_Value_Check(BaseRule):
    rule_id   = "C006"
    rule_name = "Invoice Total = Sum of Line Items"
    group     = GROUP_C

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: Invoice missing.")
        items = state.invoice_raw.get("line_items", [])
        if not items:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: No line items found in Invoice.")
        lines_sum  = sum(float(i.get("total_line", 0)) for i in items)
        total_val  = float(state.invoice_raw.get("financials", {}).get("total_value", 0))
        if total_val == 0:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: total_value is 0.")
        delta_pct = abs(lines_sum - total_val) / total_val * 100
        if delta_pct <= 1.0:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_C,
                                      f"Invoice total {total_val} matches line items sum "
                                      f"{round(lines_sum,2)} (Δ{round(delta_pct,2)}%).",
                                      ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_C,
                                  Severity.HIGH,
                                  f"Invoice total {total_val} ≠ line items sum {round(lines_sum,2)} "
                                  f"(Δ{round(delta_pct,2)}%). Possible arithmetic error or hidden charges.",
                                  ["INVOICE"],
                                  detail={"total": total_val, "lines_sum": round(lines_sum,2)})


class C007_Price_Per_KG_Check(BaseRule):
    rule_id   = "C007"
    rule_name = "Price per KG Undervaluation Risk"
    group     = GROUP_C

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: Invoice missing.")
        n = state.normalized
        hs2 = n.hs_code[:2] if len(n.hs_code) >= 2 else ""
        floor = HS_PRICE_FLOOR.get(hs2)
        if floor is None:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       f"Skipped: No price floor defined for HS prefix '{hs2}'.")
        if n.gross_weight_kg == 0 or n.total_value == 0:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_C,
                                       "Skipped: weight or value is 0.")
        ppkg = n.total_value / n.gross_weight_kg
        if ppkg >= floor:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_C,
                                      f"Price/kg={round(ppkg,2)} {n.currency} ≥ floor {floor} "
                                      f"for HS {n.hs_code}.", ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_C,
                                  Severity.HIGH,
                                  f"Undervaluation risk: {round(ppkg,2)} {n.currency}/kg for HS {n.hs_code} "
                                  f"(floor: {floor} {n.currency}/kg). High risk of customs value adjustment.",
                                  ["INVOICE"],
                                  detail={"price_per_kg": round(ppkg,2), "floor": floor,
                                          "hs_code": n.hs_code, "currency": n.currency})


GROUP_C_RULES: list[BaseRule] = [
    C001_Invoice_Number_In_CMR(), C002_Currency_Present(), C003_Incoterms_Present(),
    C004_Incoterms_Consistent(), C005_Unit_Price_Valid(),
    C006_Total_Value_Check(), C007_Price_Per_KG_Check(),
]


# ══════════════════════════════════════════════════════════════════
# GROUP D — LOGISTICS CONSISTENCY
# ══════════════════════════════════════════════════════════════════
GROUP_D = "D"
MAX_WEIGHT_TIR_KG = 24_000.0


class D001_Loading_Place_Present(BaseRule):
    rule_id   = "D001"
    rule_name = "Loading Place Present"
    group     = GROUP_D

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D, "Skipped: CMR missing.")
        n = state.normalized
        if n.loading_country:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_D,
                                      f"Loading place present: {n.loading_country}.", ["CMR"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.MEDIUM,
                                  "Loading place/country missing from CMR.", ["CMR"])


class D002_Destination_Present(BaseRule):
    rule_id   = "D002"
    rule_name = "Destination Present"
    group     = GROUP_D

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D, "Skipped: CMR missing.")
        n = state.normalized
        if n.destination_country:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_D,
                                      f"Destination present: {n.destination_country}.", ["CMR"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.MEDIUM,
                                  "Destination missing from CMR.", ["CMR"])


class D003_Carrier_Present(BaseRule):
    rule_id   = "D003"
    rule_name = "Carrier Present"
    group     = GROUP_D

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D, "Skipped: CMR missing.")
        n = state.normalized
        if n.carrier_name:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_D,
                                      f"Carrier: {n.carrier_name}.", ["CMR"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.LOW,
                                  "Carrier name missing from CMR.", ["CMR"])


class D004_Vehicle_Present(BaseRule):
    rule_id   = "D004"
    rule_name = "Vehicle Number Present"
    group     = GROUP_D

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D, "Skipped: CMR missing.")
        n = state.normalized
        if n.vehicle_number:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_D,
                                      f"Vehicle: {n.vehicle_number}.", ["CMR"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.LOW,
                                  "Vehicle number missing from CMR.", ["CMR"])


class D005_Overweight_Check(BaseRule):
    rule_id   = "D005"
    rule_name = "TIR Overweight Check (max 24,000 kg)"
    group     = GROUP_D

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D, "Skipped: CMR missing.")
        w = float(state.cmr_raw.get("gross_weight_kg", 0))
        if w == 0:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D,
                                       "Skipped: gross weight not available.")
        if w <= MAX_WEIGHT_TIR_KG:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_D,
                                      f"Weight {w}kg within TIR limit ({MAX_WEIGHT_TIR_KG}kg).", ["CMR"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.CRITICAL,
                                  f"OVERWEIGHT: {w}kg exceeds TIR road limit of {MAX_WEIGHT_TIR_KG}kg. "
                                  f"Excess: {round(w - MAX_WEIGHT_TIR_KG)}kg.",
                                  ["CMR"], detail={"weight_kg": w, "limit_kg": MAX_WEIGHT_TIR_KG})


class D006_Impossible_Density(BaseRule):
    rule_id   = "D006"
    rule_name = "Impossible Density Check"
    group     = GROUP_D

    def check(self, state: PipelineState) -> AuditResult:
        n = state.normalized
        if n.gross_weight_kg == 0 or n.volume_cbm == 0:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D,
                                       "Skipped: weight or volume not available.")
        hs2 = n.hs_code[:2] if len(n.hs_code) >= 2 else ""
        density_range = HS_DENSITY_RANGES.get(hs2)
        if density_range is None:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D,
                                       f"Skipped: No density range for HS prefix '{hs2}'.")
        density = n.gross_weight_kg / n.volume_cbm
        d_min, d_max = density_range
        if d_min <= density <= d_max:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_D,
                                      f"Density {round(density)}kg/m³ is realistic for HS {n.hs_code} "
                                      f"(range: {d_min}–{d_max}).", ["CMR", "PACKING_LIST"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.HIGH,
                                  f"Impossible density: {round(density)}kg/m³ for HS {n.hs_code}. "
                                  f"Expected range: {d_min}–{d_max}kg/m³. "
                                  f"Possible weight/volume error or wrong HS code.",
                                  ["CMR", "PACKING_LIST"],
                                  detail={"density": round(density), "hs2": hs2,
                                          "range": density_range})


class D007_Date_Not_Future(BaseRule):
    rule_id   = "D007"
    rule_name = "CMR Date Not in Future"
    group     = GROUP_D

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D, "Skipped: CMR missing.")
        from datetime import date
        cmr_date_str = state.normalized.cmr_date
        if not cmr_date_str:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.HIGH,
                                      "CMR date is missing.", ["CMR"])
        try:
            cmr_date = date.fromisoformat(cmr_date_str)
            if cmr_date <= date.today():
                return AuditResult.passed(self.rule_id, self.rule_name, GROUP_D,
                                          f"CMR date {cmr_date_str} is valid.", ["CMR"])
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.HIGH,
                                      f"CMR date {cmr_date_str} is in the future. Data error.",
                                      ["CMR"], detail={"cmr_date": cmr_date_str})
        except ValueError:
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.MEDIUM,
                                      f"CMR date '{cmr_date_str}' could not be parsed.", ["CMR"])


class D008_CMR_Date_After_Invoice(BaseRule):
    rule_id   = "D008"
    rule_name = "CMR Date ≥ Invoice Date"
    group     = GROUP_D

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr() or not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D,
                                       "Skipped: CMR or Invoice missing.")
        from datetime import date
        n = state.normalized
        try:
            cmr_d = date.fromisoformat(n.cmr_date)
            inv_d = date.fromisoformat(n.invoice_date)
            if cmr_d >= inv_d:
                return AuditResult.passed(self.rule_id, self.rule_name, GROUP_D,
                                          f"CMR date ({n.cmr_date}) ≥ Invoice date ({n.invoice_date}).",
                                          ["CMR", "INVOICE"])
            return AuditResult.failed(self.rule_id, self.rule_name, GROUP_D, Severity.MEDIUM,
                                      f"CMR date ({n.cmr_date}) is before Invoice date ({n.invoice_date}). "
                                      f"Goods cannot be shipped before invoice is issued.",
                                      ["CMR", "INVOICE"],
                                      detail={"cmr_date": n.cmr_date, "invoice_date": n.invoice_date})
        except (ValueError, TypeError):
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_D,
                                       "Skipped: dates could not be compared.")


GROUP_D_RULES: list[BaseRule] = [
    D001_Loading_Place_Present(), D002_Destination_Present(),
    D003_Carrier_Present(), D004_Vehicle_Present(),
    D005_Overweight_Check(), D006_Impossible_Density(),
    D007_Date_Not_Future(), D008_CMR_Date_After_Invoice(),
]


# ══════════════════════════════════════════════════════════════════
# GROUP E — CUSTOMS ENGINE
# ══════════════════════════════════════════════════════════════════
GROUP_E = "E"

# Санкционные страны (упрощённый список — дополнить из OFAC/EU)
SANCTIONED_COUNTRIES = {"RU", "BY", "KP", "IR", "SY", "CU", "VE"}


class E001_HS_Present(BaseRule):
    rule_id   = "E001"
    rule_name = "HS Code Present in Invoice"
    group     = GROUP_E

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_E, "Skipped: Invoice missing.")
        n = state.normalized
        if n.hs_code:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_E,
                                      f"HS Code present: {n.hs_code}.", ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_E, Severity.CRITICAL,
                                  "HS Code is missing from Invoice. Cannot calculate customs duties.",
                                  ["INVOICE"])


class E002_Origin_Country_Present(BaseRule):
    rule_id   = "E002"
    rule_name = "Country of Origin Present"
    group     = GROUP_E

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_invoice():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_E, "Skipped: Invoice missing.")
        origin = state.invoice_raw.get("shipment", {}).get("origin_country", "")
        if origin:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_E,
                                      f"Country of origin: {origin}.", ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_E, Severity.HIGH,
                                  "Country of origin missing from Invoice. "
                                  "Required for tariff classification and preferential duty rates.",
                                  ["INVOICE"])


class E003_Undervaluation_Risk(BaseRule):
    """Дублирует C007 но с фокусом на таможенный риск — другое сообщение и группа."""
    rule_id   = "E003"
    rule_name = "Customs Undervaluation Risk"
    group     = GROUP_E

    def check(self, state: PipelineState) -> AuditResult:
        n = state.normalized
        hs2  = n.hs_code[:2] if len(n.hs_code) >= 2 else ""
        floor = HS_PRICE_FLOOR.get(hs2)
        if floor is None or n.gross_weight_kg == 0 or n.total_value == 0:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_E,
                                       "Skipped: insufficient data for undervaluation check.")
        ppkg = n.total_value / n.gross_weight_kg
        if ppkg >= floor:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_E,
                                      f"Declared value {round(ppkg,2)}/kg is above customs floor.",
                                      ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_E, Severity.HIGH,
                                  f"CUSTOMS RISK: Declared {round(ppkg,2)} {n.currency}/kg for HS {n.hs_code}. "
                                  f"Customs floor is {floor} {n.currency}/kg. "
                                  f"High probability of Customs Value Adjustment (CVA).",
                                  ["INVOICE"],
                                  detail={"declared_per_kg": round(ppkg,2),
                                          "floor_per_kg": floor, "currency": n.currency})


class E004_HS_Format_Valid(BaseRule):
    rule_id   = "E004"
    rule_name = "HS Code Format Valid (6+ digits)"
    group     = GROUP_E

    def check(self, state: PipelineState) -> AuditResult:
        n = state.normalized
        hs = n.hs_code.replace(".", "").strip()
        if not hs:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_E,
                                       "Skipped: HS code not available (covered by E001).")
        if hs.isdigit() and len(hs) >= 6:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_E,
                                      f"HS Code '{hs}' format is valid.", ["INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_E, Severity.HIGH,
                                  f"HS Code '{hs}' is invalid: must be 6+ digits only.",
                                  ["INVOICE"], detail={"hs_code": hs})


class E005_Sanctions_Country_Check(BaseRule):
    rule_id   = "E005"
    rule_name = "Sanctioned Country Check"
    group     = GROUP_E

    def check(self, state: PipelineState) -> AuditResult:
        n = state.normalized
        all_countries = {
            n.shipper_country, n.consignee_country,
            n.loading_country, n.destination_country,
        } | set(n.transit_countries)
        all_countries = {c.upper() for c in all_countries if c}

        hits = all_countries & SANCTIONED_COUNTRIES
        if not hits:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_E,
                                      "No sanctioned countries detected in shipment route.",
                                      ["CMR", "INVOICE"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_E, Severity.CRITICAL,
                                  f"SANCTIONS ALERT: Sanctioned country/countries detected: "
                                  f"{', '.join(sorted(hits))}. Immediate compliance review required.",
                                  ["CMR", "INVOICE"],
                                  detail={"sanctioned_hits": sorted(hits)})


class E006_Transit_Sanctions_Check(BaseRule):
    rule_id   = "E006"
    rule_name = "Transit Route Sanctions Check"
    group     = GROUP_E

    def check(self, state: PipelineState) -> AuditResult:
        if not state.has_cmr():
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_E, "Skipped: CMR missing.")
        transit = [c.upper() for c in state.normalized.transit_countries]
        if not transit:
            return AuditResult.skipped(self.rule_id, self.rule_name, GROUP_E,
                                       "Skipped: No transit countries specified in CMR.")
        hits = set(transit) & SANCTIONED_COUNTRIES
        if not hits:
            return AuditResult.passed(self.rule_id, self.rule_name, GROUP_E,
                                      f"Transit route clear: {' → '.join(transit)}.", ["CMR"])
        return AuditResult.failed(self.rule_id, self.rule_name, GROUP_E, Severity.HIGH,
                                  f"Transit through sanctioned country: {', '.join(sorted(hits))}. "
                                  f"Re-routing may be required.",
                                  ["CMR"], detail={"transit": transit, "hits": sorted(hits)})


GROUP_E_RULES: list[BaseRule] = [
    E001_HS_Present(), E002_Origin_Country_Present(),
    E003_Undervaluation_Risk(), E004_HS_Format_Valid(),
    E005_Sanctions_Country_Check(), E006_Transit_Sanctions_Check(),
]

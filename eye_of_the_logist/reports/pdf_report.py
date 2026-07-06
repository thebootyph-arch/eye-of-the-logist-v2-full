"""
PDF Report Generator — создаёт профессиональный отчёт по результатам аудита.
Использует ReportLab. Без внешних зависимостей кроме reportlab.
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from audit.base_rule import Status, Severity
from state.pipeline_state import PipelineState

# ── Цвета ─────────────────────────────────────────────────────────
C_DARK    = colors.HexColor("#1a1a2e")
C_PRIMARY = colors.HexColor("#16213e")
C_ACCENT  = colors.HexColor("#0f3460")
C_GREEN   = colors.HexColor("#2ecc71")
C_YELLOW  = colors.HexColor("#f39c12")
C_RED     = colors.HexColor("#e74c3c")
C_GRAY    = colors.HexColor("#95a5a6")
C_LIGHT   = colors.HexColor("#ecf0f1")
C_WHITE   = colors.white

SEVERITY_COLORS = {
    Severity.CRITICAL: C_RED,
    Severity.HIGH:     colors.HexColor("#e67e22"),
    Severity.MEDIUM:   C_YELLOW,
    Severity.LOW:      colors.HexColor("#3498db"),
    Severity.INFO:     C_GRAY,
}

DECISION_COLORS = {
    "APPROVED":             C_GREEN,
    "CONDITIONAL_APPROVAL": C_YELLOW,
    "REJECTED":             C_RED,
}


class PDFReportGenerator:

    def generate(self, state: PipelineState) -> bytes:
        """Генерирует PDF отчёт, возвращает bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )
        styles = self._build_styles()
        story  = self._build_story(state, styles)
        doc.build(story)
        return buffer.getvalue()

    # ── Story builder ─────────────────────────────────────────────
    def _build_story(self, state: PipelineState, styles) -> list:
        story = []
        n     = state.normalized

        # Header
        story += self._header(state, styles)
        story.append(Spacer(1, 0.5*cm))

        # Decision banner
        story += self._decision_banner(state, styles)
        story.append(Spacer(1, 0.5*cm))

        # Risk score
        story += self._risk_section(state, styles)
        story.append(Spacer(1, 0.5*cm))

        # Shipment details
        story += self._shipment_section(state, styles)
        story.append(Spacer(1, 0.5*cm))

        # Audit results table
        story += self._audit_table(state, styles)
        story.append(Spacer(1, 0.5*cm))

        # Rejection reasons
        if state.decision != "APPROVED":
            story += self._rejection_section(state, styles)

        # Footer
        story += self._footer(styles)
        return story

    def _header(self, state: PipelineState, styles) -> list:
        items = []
        items.append(Paragraph("🐺 EYE OF THE LOGIST", styles["title"]))
        items.append(Paragraph("AI-Powered Logistics Document Audit Report", styles["subtitle"]))
        items.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT))
        items.append(Spacer(1, 0.3*cm))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        items.append(Paragraph(f"Generated: {ts}  |  Pipeline v{state.pipeline_version}",
                               styles["meta"]))
        return items

    def _decision_banner(self, state: PipelineState, styles) -> list:
        color  = DECISION_COLORS.get(state.decision, C_GRAY)
        labels = {
            "APPROVED":             "✅  DOCUMENT SET APPROVED",
            "CONDITIONAL_APPROVAL": "⚠️  CONDITIONAL APPROVAL — Review Required",
            "REJECTED":             "❌  DOCUMENT SET REJECTED",
        }
        label = labels.get(state.decision, state.decision)
        data  = [[Paragraph(label, styles["banner"])]]
        t = Table(data, colWidths=[17*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), color),
            ("TEXTCOLOR",  (0,0), (-1,-1), C_WHITE),
            ("ALIGN",      (0,0), (-1,-1), "CENTER"),
            ("TOPPADDING",    (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("ROUNDEDCORNERS", [4]),
        ]))
        return [t]

    def _risk_section(self, state: PipelineState, styles) -> list:
        score  = state.risk_score
        failed = [r for r in state.audit_results if r.status == Status.FAIL]
        passed = [r for r in state.audit_results if r.status == Status.PASS]
        skipped= [r for r in state.audit_results if r.status == Status.SKIP]

        data = [
            ["Risk Score", "Rules Passed", "Rules Failed", "Rules Skipped"],
            [
                Paragraph(f"<b>{score}/100</b>", styles["score"]),
                Paragraph(f"<font color='#2ecc71'>{len(passed)}</font>", styles["cell_c"]),
                Paragraph(f"<font color='#e74c3c'>{len(failed)}</font>", styles["cell_c"]),
                Paragraph(f"<font color='#95a5a6'>{len(skipped)}</font>", styles["cell_c"]),
            ],
        ]
        t = Table(data, colWidths=[4.25*cm]*4)
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0),  C_PRIMARY),
            ("TEXTCOLOR",   (0,0), (-1,0),  C_WHITE),
            ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
            ("ALIGN",       (0,0), (-1,-1), "CENTER"),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("GRID",        (0,0), (-1,-1), 0.5, C_LIGHT),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ]))
        return [Paragraph("Risk Assessment", styles["section"]), Spacer(1, 0.2*cm), t]

    def _shipment_section(self, state: PipelineState, styles) -> list:
        n = state.normalized
        rows = [
            ["Field", "Value"],
            ["Shipper",      f"{n.shipper_name} ({n.shipper_country})"],
            ["Consignee",    f"{n.consignee_name} ({n.consignee_country})"],
            ["Route",        f"{n.loading_country} → {n.destination_country}"],
            ["HS Code",      n.hs_code or "—"],
            ["Cargo",        (n.cargo_description or "—")[:80]],
            ["Gross Weight", f"{n.gross_weight_kg} kg"],
            ["Volume",       f"{n.volume_cbm} m³"],
            ["Packages",     str(n.packages_count)],
            ["Total Value",  f"{n.total_value} {n.currency}"],
            ["Incoterms",    n.incoterms or "—"],
            ["CMR Date",     n.cmr_date or "—"],
            ["Invoice Date", n.invoice_date or "—"],
        ]
        col_w = [5*cm, 12*cm]
        t = Table(rows, colWidths=col_w)
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0),  C_PRIMARY),
            ("TEXTCOLOR",   (0,0), (-1,0),  C_WHITE),
            ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
            ("BACKGROUND",  (0,1), (-1,-1), C_LIGHT),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_WHITE, C_LIGHT]),
            ("GRID",        (0,0), (-1,-1), 0.5, C_GRAY),
            ("ALIGN",       (0,0), (0,-1),  "RIGHT"),
            ("FONTNAME",    (0,1), (0,-1),  "Helvetica-Bold"),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        return [Paragraph("Shipment Details", styles["section"]), Spacer(1, 0.2*cm), t]

    def _audit_table(self, state: PipelineState, styles) -> list:
        header = ["Rule ID", "Name", "Status", "Severity", "Message"]
        rows   = [header]

        for r in state.audit_results:
            if r.status == Status.SKIP:
                continue
            status_str = "✅ PASS" if r.status == Status.PASS else "❌ FAIL"
            rows.append([
                r.rule_id,
                r.rule_name,
                status_str,
                r.severity.value,
                r.message[:90] + ("…" if len(r.message) > 90 else ""),
            ])

        col_w = [1.5*cm, 3.5*cm, 2*cm, 2.2*cm, 7.8*cm]
        t = Table(rows, colWidths=col_w, repeatRows=1)

        style = [
            ("BACKGROUND",  (0,0), (-1,0),  C_PRIMARY),
            ("TEXTCOLOR",   (0,0), (-1,0),  C_WHITE),
            ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 7),
            ("GRID",        (0,0), (-1,-1), 0.3, C_GRAY),
            ("VALIGN",      (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_WHITE, C_LIGHT]),
        ]

        # Подсветка FAIL строк
        for i, r in enumerate(state.audit_results, start=1):
            if r.status == Status.FAIL:
                c = SEVERITY_COLORS.get(r.severity, C_GRAY)
                style.append(("BACKGROUND", (2, i), (3, i), c))
                style.append(("TEXTCOLOR",  (2, i), (3, i), C_WHITE))

        t.setStyle(TableStyle(style))
        return [Paragraph("Audit Results", styles["section"]), Spacer(1, 0.2*cm), t]

    def _rejection_section(self, state: PipelineState, styles) -> list:
        items = [Paragraph("Issues Requiring Attention", styles["section"])]
        failed = [r for r in state.audit_results if r.status == Status.FAIL]
        for r in failed:
            c = SEVERITY_COLORS.get(r.severity, C_GRAY)
            items.append(
                Paragraph(
                    f"<font color='#{_hex(c)}'><b>[{r.rule_id}] {r.severity.value}</b></font> "
                    f"— {r.message}",
                    styles["issue"],
                )
            )
            items.append(Spacer(1, 0.1*cm))
        return items

    def _footer(self, styles) -> list:
        return [
            Spacer(1, 0.5*cm),
            HRFlowable(width="100%", thickness=1, color=C_GRAY),
            Paragraph(
                "Eye of the Logist — AI-Powered Logistics Compliance Platform  |  "
                "This report is generated automatically and should be reviewed by a qualified specialist.",
                styles["footer"],
            ),
        ]

    # ── Styles ────────────────────────────────────────────────────
    @staticmethod
    def _build_styles():
        base = getSampleStyleSheet()
        s = {}
        s["title"] = ParagraphStyle("title", parent=base["Normal"],
            fontSize=22, fontName="Helvetica-Bold",
            textColor=C_DARK, spaceAfter=4, alignment=TA_LEFT)
        s["subtitle"] = ParagraphStyle("subtitle", parent=base["Normal"],
            fontSize=10, textColor=C_GRAY, spaceAfter=6)
        s["meta"] = ParagraphStyle("meta", parent=base["Normal"],
            fontSize=8, textColor=C_GRAY)
        s["section"] = ParagraphStyle("section", parent=base["Normal"],
            fontSize=12, fontName="Helvetica-Bold",
            textColor=C_PRIMARY, spaceBefore=6, spaceAfter=4)
        s["banner"] = ParagraphStyle("banner", parent=base["Normal"],
            fontSize=16, fontName="Helvetica-Bold",
            textColor=C_WHITE, alignment=TA_CENTER)
        s["score"] = ParagraphStyle("score", parent=base["Normal"],
            fontSize=24, fontName="Helvetica-Bold",
            textColor=C_DARK, alignment=TA_CENTER)
        s["cell_c"] = ParagraphStyle("cell_c", parent=base["Normal"],
            fontSize=18, fontName="Helvetica-Bold", alignment=TA_CENTER)
        s["issue"] = ParagraphStyle("issue", parent=base["Normal"],
            fontSize=8, leading=12)
        s["footer"] = ParagraphStyle("footer", parent=base["Normal"],
            fontSize=7, textColor=C_GRAY, alignment=TA_CENTER, spaceBefore=4)
        return s


def _hex(color) -> str:
    """ReportLab Color → hex string без #."""
    r = int(color.red * 255)
    g = int(color.green * 255)
    b = int(color.blue * 255)
    return f"{r:02x}{g:02x}{b:02x}"

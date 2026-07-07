"""
Eye of the Logist — Streamlit UI v2
Full pipeline: Upload → Classify → Parse → Normalize → Audit → Report
"""
import asyncio
import logging
import time
import json

import streamlit as st

logging.basicConfig(level=logging.ERROR)

# ── Page config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Eye of the Logist",
    page_icon="🐺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .metric-card {
        background: white; border-radius: 8px; padding: 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08); text-align: center;
    }
    .approved  { background: #d5f5e3; border-left: 5px solid #2ecc71; padding: 12px; border-radius: 4px; }
    .rejected  { background: #fadbd8; border-left: 5px solid #e74c3c; padding: 12px; border-radius: 4px; }
    .cond      { background: #fef9e7; border-left: 5px solid #f39c12; padding: 12px; border-radius: 4px; }
    .rule-pass { color: #2ecc71; font-weight: bold; }
    .rule-fail { color: #e74c3c; font-weight: bold; }
    .rule-skip { color: #95a5a6; }
</style>
""", unsafe_allow_html=True)


# ── Imports (после page config) ───────────────────────────────────
from agents.classifier import DocumentClassifier
from agents.parsers.cmr_parser import CMRParser
from agents.parsers.invoice_parser import InvoiceParser
from agents.parsers.packing_list_parser import PackingListParser
from agents.parsers.base_parser import ParserConfig
from agents.normalizer import Normalizer
from audit.auditor import CrossDocumentAuditor
from audit.base_rule import Status, Severity
from engine.risk_engine import RiskEngine, DecisionEngine
from reports.json_report import JSONReportGenerator, ERPExportGenerator
from reports.pdf_report import PDFReportGenerator
from state.pipeline_state import PipelineState


# ── Pipeline runner ───────────────────────────────────────────────
async def run_full_pipeline(
    files: list[tuple[bytes, str, str]],   # (bytes, mime, filename)
    config: ParserConfig,
    progress_cb,
) -> PipelineState:
    state = PipelineState()
    classifier = DocumentClassifier(config)

    # Step 1: Classify
    progress_cb(0.1, "🔍 Classifying documents...")
    doc_map: dict[str, tuple[bytes, str]] = {}

    for file_bytes, mime_type, filename in files:
        doc_type = await classifier.classify(file_bytes, mime_type)
        doc_map[doc_type] = (file_bytes, mime_type)

    # Step 2: Parse (параллельно)
    progress_cb(0.3, "🤖 Parsing with Gemini AI...")
    parsers = {
        "CMR":          CMRParser(config),
        "INVOICE":      InvoiceParser(config),
        "PACKING_LIST": PackingListParser(config),
    }

    async def parse_one(doc_type: str, file_bytes: bytes, mime: str):
        parser = parsers.get(doc_type)
        if not parser:
            return doc_type, {}, 0.0
        data, conf = await parser.parse(file_bytes, mime)
        return doc_type, data, conf

    tasks = [parse_one(dt, fb, mt) for dt, (fb, mt) in doc_map.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            state.add_error(str(result))
            continue
        doc_type, data, conf = result
        if doc_type == "CMR":
            state.cmr_raw = data
            state.cmr_confidence = conf
        elif doc_type == "INVOICE":
            state.invoice_raw = data
            state.invoice_confidence = conf
        elif doc_type == "PACKING_LIST":
            state.packing_list_raw = data
            state.packing_list_confidence = conf

    # Step 3: Normalize
    progress_cb(0.55, "⚙️ Normalizing data...")
    state.normalized = Normalizer().normalize(state)

    # Step 4: Audit
    progress_cb(0.70, "🕵️ Running cross-document audit...")
    CrossDocumentAuditor().run(state)

    # Step 5: Risk + Decision
    progress_cb(0.90, "📊 Calculating risk score...")
    RiskEngine().calculate(state)
    DecisionEngine().decide(state)

    progress_cb(1.0, "✅ Done!")
    return state


# ── UI ────────────────────────────────────────────────────────────
def main():
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/wolf.png", width=64)
        st.title("Eye of the Logist")
        st.caption("AI Logistics Audit Platform v2.0")
        st.divider()

        api_key = st.text_input(
            "🔑 Gemini API Key",
            type="password",
            placeholder="AIza...",
            help="Google AI Studio key. Get it at aistudio.google.com",
        )

        st.divider()
        st.markdown("**How it works:**")
        st.markdown("1. Upload CMR + Invoice + Packing List")
        st.markdown("2. AI extracts all fields")
        st.markdown("3. 40+ audit rules check consistency")
        st.markdown("4. Risk score & decision in seconds")
        st.divider()
        st.caption("🔒 Your documents are not stored.")

    # Main area
    st.title("🐺 Eye of the Logist")
    st.markdown("*AI-Powered Cross-Document Logistics Audit*")

    if not api_key:
        st.warning("👈 Enter your Gemini API Key in the sidebar to start.")
        st.stop()

    # Upload zone
    st.subheader("📂 Upload Document Set")
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        f_cmr = st.file_uploader("CMR (Waybill)", type=["pdf","png","jpg","jpeg"],
                                  key="cmr")
    with col_u2:
        f_inv = st.file_uploader("Commercial Invoice", type=["pdf","png","jpg","jpeg"],
                                  key="inv")
    with col_u3:
        f_pl  = st.file_uploader("Packing List", type=["pdf","png","jpg","jpeg"],
                                  key="pl")

    uploaded = [f for f in [f_cmr, f_inv, f_pl] if f is not None]

    if len(uploaded) < 2:
        st.info("Upload at least 2 documents to run the audit.")
        st.stop()

    st.success(f"✅ {len(uploaded)}/3 documents uploaded.")

    # Run button
    if st.button("👁️ Run Full Audit", type="primary", use_container_width=True):
        config = ParserConfig(api_key=api_key.strip())
        files  = [(f.getvalue(), f.type, f.name) for f in uploaded]

        progress_bar  = st.progress(0)
        status_text   = st.empty()

        def progress_cb(pct: float, msg: str):
            progress_bar.progress(pct)
            status_text.text(msg)

        start = time.time()
        try:
            state = asyncio.run(run_full_pipeline(files, config, progress_cb))
            elapsed = round(time.time() - start, 1)
            st.session_state["state"]   = state
            st.session_state["elapsed"] = elapsed
            progress_bar.empty()
            status_text.empty()
        except Exception as e:
            st.error(f"❌ Pipeline error: {e}")
            st.stop()

    # ── Results ───────────────────────────────────────────────────
    if "state" not in st.session_state:
        st.stop()

    state   : PipelineState = st.session_state["state"]
    elapsed : float         = st.session_state["elapsed"]
    n = state.normalized

    st.divider()

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⏱️ Audit Time",      f"{elapsed}s",       "vs ~15 min manual")
    c2.metric("📋 Rules Checked",   len(state.audit_results))
    c3.metric("🎯 Risk Score",      f"{state.risk_score}/100")
    c4.metric("💰 AI Cost",         "~$0.003")

    # Decision banner
    st.divider()
    if state.decision == "APPROVED":
        st.markdown('<div class="approved"><h3>✅ APPROVED — Document set passed all checks.</h3></div>',
                    unsafe_allow_html=True)
    elif state.decision == "CONDITIONAL_APPROVAL":
        st.markdown('<div class="cond"><h3>⚠️ CONDITIONAL APPROVAL — Issues found, review required.</h3></div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="rejected"><h3>❌ REJECTED — Document set failed compliance audit.</h3></div>',
                    unsafe_allow_html=True)

    st.divider()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📦 Shipment", "🕵️ Audit Results", "📊 Raw Data", "📥 Export"])

    with tab1:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Parties**")
            st.markdown(f"📤 **Shipper:** {n.shipper_name} `{n.shipper_country}`")
            st.markdown(f"   Tax ID: `{n.shipper_tax_id or '—'}`")
            st.markdown(f"📥 **Consignee:** {n.consignee_name} `{n.consignee_country}`")
            st.markdown(f"   Tax ID: `{n.consignee_tax_id or '—'}`")
            st.divider()
            st.markdown("**Route**")
            st.markdown(f"🗺️ `{n.loading_country}` → `{n.destination_country}`")
            if n.transit_countries:
                st.markdown(f"   Transit: {' → '.join(n.transit_countries)}")
        with col_b:
            st.markdown("**Cargo**")
            st.markdown(f"📦 {n.cargo_description or '—'}")
            st.markdown(f"HS Code: `{n.hs_code or '—'}`")
            st.markdown(f"⚖️ {n.gross_weight_kg} kg gross / {n.net_weight_kg} kg net")
            st.markdown(f"📐 {n.volume_cbm} m³  |  {n.packages_count} packages")
            st.divider()
            st.markdown("**Financials**")
            st.markdown(f"💰 {n.total_value} {n.currency}  |  {n.incoterms}")
            st.markdown(f"Price/kg: {n.price_per_kg} {n.currency}")

    with tab2:
        # Summary
        col_f, col_p, col_s = st.columns(3)
        failed  = [r for r in state.audit_results if r.status == Status.FAIL]
        passed  = [r for r in state.audit_results if r.status == Status.PASS]
        skipped = [r for r in state.audit_results if r.status == Status.SKIP]
        col_f.metric("❌ Failed",  len(failed))
        col_p.metric("✅ Passed",  len(passed))
        col_s.metric("⏭️ Skipped", len(skipped))

        # Failed rules first
        if failed:
            st.markdown("**🔴 Issues Found:**")
            for r in sorted(failed, key=lambda x: (x.severity.value, x.rule_id)):
                sev_emoji = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🔵"}.get(r.severity.value,"⚪")
                with st.expander(f"{sev_emoji} [{r.rule_id}] {r.rule_name} — {r.severity.value}"):
                    st.write(r.message)
                    if r.detail:
                        st.json(r.detail)

        # Passed rules (collapsed)
        with st.expander(f"✅ {len(passed)} rules passed"):
            for r in passed:
                st.markdown(f"- `{r.rule_id}` {r.rule_name}")

    with tab3:
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            st.caption("CMR Raw")
            st.json(state.cmr_raw)
        with col_r2:
            st.caption("Invoice Raw")
            st.json(state.invoice_raw)
        with col_r3:
            st.caption("Packing List Raw")
            st.json(state.packing_list_raw)

    with tab4:
        st.markdown("**Download Reports**")
        col_d1, col_d2, col_d3 = st.columns(3)

        # JSON
        json_str = JSONReportGenerator().generate(state)
        col_d1.download_button(
            "📄 Download JSON Report",
            data=json_str,
            file_name="audit_report.json",
            mime="application/json",
            use_container_width=True,
        )

        # ERP / SAP
        erp_str = ERPExportGenerator().generate(state)
        col_d2.download_button(
            "🏭 Download ERP/SAP Export",
            data=erp_str,
            file_name="erp_export.json",
            mime="application/json",
            use_container_width=True,
        )

        # PDF
        try:
            pdf_bytes = PDFReportGenerator().generate(state)
            col_d3.download_button(
                "📋 Download PDF Report",
                data=pdf_bytes,
                file_name="audit_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            col_d3.warning(f"PDF generation failed: {e}")

    # Errors
    if state.errors:
        st.divider()
        with st.expander("⚠️ Pipeline Errors"):
            for err in state.errors:
                st.error(err)

    st.divider()
    st.info("💡 Want to integrate this into your logistics system? "
            "[Connect on LinkedIn](https://linkedin.com)")


if __name__ == "__main__":
    main()

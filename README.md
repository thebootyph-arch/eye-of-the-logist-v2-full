# Eye of the Logist: Intelligent Document Processing (IDP) & Compliance Risk Engine

An autonomous, enterprise-grade AI solution designed to automate supply chain document audits, eliminate customs compliance bottlenecks, and mitigate trade risks. The system ingests multi-format logistics documents, extracts complex tabular data using advanced LLMs, normalizes it to international standards, and runs a strict, deterministic 40-rule audit engine.

---

## 🚀 Core Features & System Architecture

### 1. Document Ingestion Layer
*   Multi-Format Support: Seamless upload processing for PDF, PNG, and JPG files.
*   Intelligent Classification: Automated document type detection (CMR, Invoice, Packing List) driven by LLM vision/text classification with a resilient regex/keyword fallback mechanism.

### 2. Intelligent Parsing Layer (Gemini AI)
*   CMR Parser: Extracts cross-border transport data, including consignor/consignee details, routing, exact cargo descriptions, transport assets, and signature verification blocks.
*   Invoice Parser: Extracts commercial transaction data, line items, financial totals, unit prices, tax allocations, and Incoterms.
*   Packing List Parser: Extracts physical shipping configurations, packaging types, gross/net weight distributions, and manufacturing/shipping marks.
*   Data Reliability: Computes a real-time Confidence Score for every extracted field and utilizes an API polling structure with exponential backoff retry logic to handle LLM rate limits.

### 3. Data Normalization Layer
Ensures heterogeneous and messy real-world inputs are strictly standardized before passing to the validation layer:
*   Geopolitical Data: Germany / Deutschland / Federal Republic of Germany ➔ Standardized to ISO 2-letter country code DE.
*   Financial Data: Euro / € ➔ Standardized to ISO 4217 currency code EUR.
*   Trade Terms: Delivered At Place ➔ Standardized to strict DAP Incoterms syntax.
*   Temporal Data: Any unstructured layout ➔ Parsed into standard ISO 8601 extended format (2024-01-15).
*   Customs Data: 6109.10.00 ➔ Sanitized into clean 6-digit Harmonized System (HS) codes.
*   Metrics Engine: Automatic mathematical conversion from tons/lbs into standard kilograms (kg).

### 4. Deterministic Audit Engine (40 Rules Across 6 Domains)
The core of the system executes a multi-layered compliance audit composed of 40 precise rule-checks divided into specialized functional domains:
*   Domain F: Document Completeness (7 Rules): *Mandatory Gateway.* Validates presence of critical seals, signatures, and legally binding fields. Failure here triggers an immediate system block.
*   Domain A: Identity Consistency (5 Rules): Cross-document validation matching buyer, seller, carrier, and consignee data points across the entire batch.
*   Domain B: Cargo Consistency (7 Rules): Verification of physical metrics (cross-checking total weights, item counts, and descriptions between Invoice and Packing List).
*   Domain C: Commercial Consistency (7 Rules): Financial logic audits (cross-summing line items, verifying tax logic, and validating currency alignment).
*   Domain D: Logistics Consistency (8 Rules): Transport architecture audit (matching license plates, trailer IDs, port codes, and shipping routes across documents).
*   Domain E: Customs Engine (6 Rules): High-level trade compliance. Checks HS codes against international sanctions lists and detects indicators of cargo under-declaration.

### 5. Dynamic Risk & Scoring Engine
*   Composite Scoring: Evaluates total risk layout, outputting a consolidated operational score from 0 to 100.
*   Weighted Penalty System: Dynamically deducts points based on triggered rule severity:
    *   CRITICAL: −25 points
    *   HIGH: −10 points
    *   MEDIUM: −5 points
    *   LOW: −2 points
*   Automated Verdicts: Generates clean routing flags for operational workflows: APPROVED, CONDITIONAL APPROVAL, or REJECTED.

### 6. Enterprise Integration & Export
*   JSON Report: Full structural payload mapping complete metadata, triggered rule IDs, and granular confidence intervals.
*   PDF Report: C-level executive document featuring structured tables, complete violation logs, and strict color-coded risk indexing.
*   ERP/SAP Integration: Generates an intermediate IDOC-compliant schema optimized for native downstream ingestion into SAP, Oracle, or custom enterprise systems.

---

## 🛠️ Tech Stack & Interfaces

*   Core Backend: Python, FastAPI (High-performance asynchronous POST /audit REST endpoint for headless B2B automation).
*   Frontend UI: Streamlit Web App featuring a clean, human-in-the-loop dashboard mapped across 4 interactive evaluation tabs.
*   AI Infrastructure: Gemini Pro / Vision API with structured Pydantic output rendering.

---

## 🗺️ Product Roadmap

While the MVP completely satisfies early pilot parameters for single-tenant operations, the following components are prioritized for upcoming sprints:
- [ ] Role-Based Access Control (RBAC) & Multi-Tenant Authentication.
- [ ] Persistent Database Architecture (Historical audit logging, performance analytics, and trends).
- [ ] Tabular Export Formats (Excel / XLSX automated generation).
- [ ] Live customs infrastructure integration (Direct verification API calls for NCTS and MRN tracking).
- [ ] Enterprise alerting systems (Real-time Slack webhooks and email notification loops).

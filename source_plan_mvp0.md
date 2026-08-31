# EXTERNAL DATA SOURCE CATALOG — MARKET INSIGHTS AGENT MVP0

*Handoff document for DA (Bach) — scope: agent that pulls data to support the Competitor & Market Analysis section of Annual Planning*

*Version 1.0 — 26/08/2026 — CVM, RBG. Complies with Market Insights Agent spec v3.1 (sheet 04 whitelist, sheet 08 exclusions) and BRD 21/08/2026.*

---

## 1. Purpose and scope of MVP0

MVP0 does exactly one thing: pull and store all the external data needed to reconstruct the 4 content areas of the Competitor & Market Analysis section in Annual Planning:

1. Quantitative benchmarks for 5 banks: VCB, BIDV, MBB, ACB, TCB
2. Scan of CVP, offerings, and segment-based sales models
3. Strategic profile per bank
4. Macro, government, and PEST factors

MVP0 does **not analyze and does not write reports**. Every record pulled must carry the following metadata:
- Source code
- URL
- Reference period
- Date pulled
- Data basis (standalone or consolidated)
- Actual/proxy label

**Demo is considered successful when**: a full pull cycle runs for all 4 layers, the raw store has complete metadata, source errors are logged, and no record comes from a banned domain. MVP1 design starts only after the demo.

---

## 2. Source role classification rules (mandatory reading before configuration)

Every source in this catalog belongs to exactly one of four roles. The agent handles each role differently — **it must not infer this on its own**:

| Role | Definition and handling |
|---|---|
| **Citable** | Official disclosure sources (government bodies, the banks themselves, multilateral organizations, whitelisted journals). The agent ingests and stores these, and figures from here are cited in later reports. Complies with R-F02: every record must have source code, reference period, date pulled, link. |
| **Aggregator** | Intermediate repository holding official original documents (e.g. Vietstock's "Document Download" tab containing financial statements, AGM resolutions issued by the bank). The agent may use it as a download path, but the source recorded in metadata is the bank's original document, **not the aggregator site**. News articles from these sites are never ingested. |
| **Signal-scouting** | Trade press and market chatter. The agent **does not ingest this as data and does not cite figures from it**. In MVP0, scouting signals from this group is a manual, human task outside the system; any figure discovered here must be traced back to a Citable source before entering the store. |
| **Out of scope** | Metrics for which no official external disclosure source exists. The agent **does not pull these**. Data comes from TCB's internal sources and is entered manually via the data/manual path when needed, tagged as internal source. |

### Absolute banned domains per sheet 08
The agent refuses to ingest or cite from these; violation is an automatic **FAIL** for the cycle per R-G02:
- vnexpress.net
- dantri.com.vn
- tuoitre.vn
- thanhnien.vn
- facebook.com
- tiktok.com
- cafef.vn

Also banned: social media, investor forums, competitor rumors, and figures with no clear reference period (R-G03).

---

## 3. Layer 1 — Quantitative benchmark for 5 banks

### 3.1. Metrics to pull

| Metric | Definition / how to derive | Notes |
|---|---|---|
| Cumulative CASA growth (YTD/9M) | Retail customer non-term deposit balance from quarterly financial statement notes or investor deck; growth calculated vs. start of year | Prioritize retail-only figure; if unavailable, use whole-bank figure and tag as proxy |
| CASA ratio (%CASA) | CASA over total retail customer deposits | TCB, VCB, MBB, ACB disclose quarterly; BIDV only annually |
| Term deposit growth (TD + CD) | Term deposits and certificates of deposit, separate from CASA | From customer deposit notes in financial statements |
| Credit growth | Retail customer loan balance if disclosed; otherwise whole-bank figure | Note standalone vs. consolidated basis in metadata |
| Bancassurance APE 9M | See section 3.4 — out of agent scope | No official per-bank disclosure source exists |

### 3.2. Official per-bank sources (role: Citable)

| Source | Role | URL | Data pulled | Frequency | Access & notes |
|---|---|---|---|---|---|
| Techcombank (TCB) | Citable | techcombank.com/en/investors (financial-statements-vas, financial-statements-ifrs, investor-presentations, annual-report sections) | Quarterly VAS/IFRS financial statements, quarterly IR deck with retail CASA breakout, credit growth by segment (RBG/BB/WB) | Quarterly | Open PDFs, static URL pattern /content/dam/..., crawlable. English deck released ~20-30 days after period-end. Best disclosure in the group |
| Vietcombank (VCB) | Citable | portal.vietcombank.com.vn/Investors (English version: /en-us/Investors) | Quarterly financial statements, English IR deck, CASA ratio, wholesale vs. retail split | Quarterly | Oracle WebCenter portal, aspx ItemID parameters, occasional timeouts; crawler needs retry logic |
| BIDV (BID) | Citable | bidv.com.vn/vn/quan-he-nha-dau-tu/bao-cao-va-tai-lieu/ (financial statements, annual reports) | Quarterly financial statements; retail and CASA breakout only appears in the annual report | Quarterly (financials), Annual (breakdown) | NO standardized quarterly IR deck. For quarterly metrics, use whole-bank figure and mandatory proxy tag |
| MB Bank (MBB) | Citable | mbbank.com.vn/Investor/thong-bao-nha-dau-tu | Quarterly financial statements, quarterly analyst meeting materials, CASA ratio | Quarterly | Primarily Vietnamese-language navigation; medium crawl difficulty |
| ACB | Citable | acb.com.vn/en/investors (financial-statements, annual-report) | English financial statements, quarterly IR materials on CASA, NIM, credit growth; retail loan and deposit composition | Quarterly | PDF and HTML open; subsidiaries reported separately |

### 3.3. Aggregator and system-wide data

| Source | Role | URL | Data pulled | Frequency | Access & notes |
|---|---|---|---|---|---|
| VietstockFinance ("Document Download" tab) | Aggregator | finance.vietstock.vn/{ticker}/tai-tai-lieu.htm with tickers tcb, vcb, bid, mbb, acb | Financial statements, board resolutions, AGM documents and resolutions, annual reports, earnings explanation filings (original documents issued by the bank) | Event-driven | Document list is crawlable; some data fields require login and are skipped. Metadata records the bank's original document as the source |
| SBV — new portal | Citable | sbv.gov.vn (credit institution system section, interest rate section) | Core credit-institution-system indicators, LDR, NPL ratio, interest rate statistics, credit growth and credit room announcements | Monthly | Web structure has changed: old WebCenter URLs are dead, do not configure against old links |
| SBV — statistics subsystem | Citable | dttktt.sbv.gov.vn | Time-series tables: total means of payment, customer deposits at credit institutions | Monthly (2-3 month lag) | Blocks bots (robots.txt). **Do not crawl.** Manual monthly download, ingested via data/manual/G02 per the BRD-approved approach |

### 3.4. Bancassurance APE — out of agent scope for MVP0

- **Verified conclusion**: no organization officially discloses per-bank APE. The Insurance Association of Vietnam (iav.vn) only publishes total life insurance market figures monthly (new business premium, total premium).
- **Handling**: per-bank APE figures come from internal sources (Banca team, insurance partner data), entered manually, tagged as internal source. The agent only pulls the total market figure from iav.vn (role: Citable, monthly frequency, open HTML) as a benchmark denominator.
- APE articles in trade press (Tin nhanh chứng khoán and similar) are signal-scouting only, outside the system — not ingested, not cited.

---

## 4. Layer 2 — CVP, offerings, and segment-based sales models

Scan targets: VCB, BIDV, MBB, ACB, plus **VPBank** (direct competitor in the mass-affluent segment). Segments follow the slide structure: HNW/Private, AFF, MAF/EMAF, Merchants, SME.

| Source | Role | URL | Data pulled | Frequency | Access & notes |
|---|---|---|---|---|---|
| Official news/promotions pages per bank | Citable | News/Promotions section on each bank's main site: portal.vietcombank.com.vn; bidv.com.vn/vn/; mbbank.com.vn; acb.com.vn; vpbank.com.vn | Product launches, new CVPs, segment-specific perks, partnerships, promotional campaigns | Weekly | Open HTML, crawlable. This is the competitor's own official disclosure, so it's valid under R-G03 |
| Fee schedules and terms & conditions | Citable | Fee schedule and T&C pages per bank (e.g. vpbank.com.vn/-/media/... for PDF files) | Service fees, listed interest rates, product package conditions by segment | Monthly | Open PDF and HTML; compare period-over-period to catch changes |
| Google Play & Apple App Store — release notes | Citable | App pages for Techcombank Mobile, VCB Digibank, BIDV SmartBanking, MBBank, ACB ONE, VPBank NEO | Release notes (new features self-disclosed by the bank), update history | Weekly | Crawlable but must be rate-limited. Release notes are the bank's own disclosure, so citable |
| Google Play & App Store — user reviews | Signal-scouting | Same app pages as above | User sentiment on features, issues | Not ingested | User-generated content, not official disclosure. Not ingested in MVP0; reconsider in MVP1 with a dedicated framework |
| Recruitment sites (VietnamWorks, TopCV) | Signal-scouting | vietnamworks.com; topcv.vn | Signals of RM team expansion, private banking, merchant hiring via job postings | Not ingested | Manual scouting only, outside the system. LinkedIn requires login and restricts crawling: excluded from MVP0 |

---

## 5. Layer 3 — Strategic profile per bank

| Source | Role | URL | Data pulled | Frequency | Access & notes |
|---|---|---|---|---|---|
| Annual reports and AGM documents for all 5 banks | Citable | Each bank's IR page listed in 3.2, or downloaded via the Vietstock aggregator in 3.3 | Strategic direction, retail customer count, fee revenue composition, technology disclosures (core banking, open API, super app, BaaS, wallet partnerships), leadership statements | Annual (AGM in Q2, annual report in Q1-Q2) | PDF. Pulled once a year and whenever an out-of-cycle AGM document appears |
| Securities firm research reports (SSI, VNDirect, VCBS, BSC) | Citable (Tier 2) | SSI: public PDFs on ftp2.ssi.com.vn and ssi.com.vn research section; VNDirect: vndirect.com.vn/category/bao-cao-phan-tich/; VCBS: vcbs.com.vn/trung-tam-phan-tich; BSC: bsc.com.vn | Analyst views, forecasts, banking sector comparisons | Event-driven | Only publicly available PDFs are used; anything behind login is excluded. This is Tier 2 (analyst opinion): every forecast figure must be tagged "forecast" with the issuing firm named per R-F04, and [Opinion] must be separated from [Fact] per R-F07 |
| Banking Review Journal (J02), Finance Review Journal (J03) | Citable | tapchinganhang.gov.vn; tapchitaichinh.vn | Monetary policy analysis, policy framing from government bodies | Monthly | Already on the sheet 04 whitelist |
| Trade financial press (VnEconomy J01, Vietstock news, Tin nhanh chứng khoán) | Signal-scouting | vneconomy.vn; vietstock.vn; tinnhanhchungkhoan.vn | Event scouting: leadership changes, deals, technology announcements | Not ingested | Follows the finalized J01 rule: leads only, any figure must be traced back to an official source. CafeF is a banned domain and may not be used even for internal scouting |

---

## 6. Layer 4 — Macro, government, PEST

### 6.1. Monetary and credit policy

| Source | Role | URL | Data pulled | Frequency | Access & notes |
|---|---|---|---|---|---|
| SBV — legal documents and directives | Citable | sbv.gov.vn (documents section, directive news section) | Circulars on real estate lending, credit room mechanism, interest rate caps, annual credit growth targets | Monthly + event-driven | Documents currently in effect that need monitoring: Circular 08/2026/TT-NHNN; Official Letter 4551/NHNN-CSTT (effective through 2026, excludes social housing/industrial park loans from real estate credit controls); credit room allocation mechanism under Circular 52/2018. Note: the pilot roadmap to remove the credit room from 2026 is directional guidance, not a confirmed outcome — tag as forward-looking |
| Thư viện Pháp luật / LuatVietnam | Aggregator | thuvienphapluat.vn; luatvietnam.vn | Look up and track documents by reference number; the cited source is the original document from the issuing authority | Event-driven | Full text of some documents requires registration; used for discovery and lookup, metadata records the original document's reference number |

### 6.2. Government development direction

| Source | Role | URL | Data pulled | Frequency | Access & notes |
|---|---|---|---|---|---|
| Government Web Portal | Citable | chinhphu.vn | Resolutions and decrees on public investment, social housing, private sector economy, digital transformation | Monthly + event-driven | Documents to pre-configure for monitoring: Decree 94/2025 (fintech sandbox: P2P lending, credit scoring, Open API); Resolution 57-NQ/TW; Data Law and National Data Center; VNeID e-identification |

### 6.3. Income and consumer behavior

| Source | Role | URL | Data pulled | Frequency | Access & notes |
|---|---|---|---|---|---|
| General Statistics Office (formerly GSO) | Citable | gso.gov.vn (statistics section, national accounts section) | Household income and expenditure (VHLSS), CPI, GDP, labor data | Monthly (CPI), Quarterly (GDP), Annual (VHLSS) | Reorganized under the Ministry of Finance, but the gso.gov.vn website is still active; open HTML and Excel, crawlable |
| Personal income tax policy | Citable | Original documents: Resolution 110/2025/UBTVQH15 and Personal Income Tax Law 109/2025 (locate via thuvienphapluat) | New family deduction levels effective 2026 (self: 15.5 million/month, dependent: 6.2 million/month), 5-tier tax schedule | Event-driven | Directly affects disposable income, an input for the consumer behavior thesis |
| Consumer research (Cimigo, Decision Lab, Q&Me) | Citable (Tier 2) | cimigo.com (has free retail banking reports); decisionlab.co; qandme.net | Gen X/Y/Z behavior, lifestyle banking, public survey findings | Quarterly | Only publicly released portions are used; this is Tier 2 — tag as [Opinion], note the survey sample |

### 6.4. AI in banking and green finance

| Source | Role | URL | Data pulled | Frequency | Access & notes |
|---|---|---|---|---|---|
| VNBA and VietFintech | Citable | vnba.org.vn | Open banking developments, AI in banking, commentary on Decree 94 | Monthly | Already on the whitelist (N02) |
| Green credit | Citable | Official announcements on sbv.gov.vn; tapchinganhang.gov.vn | Green credit outstanding balance as disclosed by SBV; Decision 21/2025 (national green taxonomy); Circular 17/2022 (environmental risk management) | Quarterly | Green credit figures are taken only from SBV's official statements and news, never via mainstream press |

---

## 7. Pull schedule and MVP0 build roadmap

- **Phase 1 (build first)**: Layer 1. Crawlers for the 5 IR pages + Vietstock document tab, quarterly schedule targeting a 15-40 day window after period-end. SBV statistics: manual monthly download process ingested via data/manual/G02. Total bancassurance market figure from iav.vn, monthly.
- **Phase 2**: Layers 2 and 3. Weekly crawl of news/promotions pages + app store release notes (rate-limited). Annual reports and AGM documents pulled event-driven. Public securities-firm PDFs pulled event-driven.
- **Phase 3**: Layer 4. Monthly scan of sbv.gov.vn, chinhphu.vn, gso.gov.vn; track documents by reference number, flag when a new document matching the watchlist appears.

---

## 8. Technical and compliance constraints

- Respect robots.txt on every bank and government site; sources that block bots (dttktt.sbv.gov.vn) switch entirely to the manual ingestion path — no workarounds.
- Rate-limit when pulling from app stores and bank portals; the crawler must retry and log each run per R-F01.
- No personal data is collected under any circumstance (per Decree 13/2023 on personal data protection); only corporate and public market data is pulled.
- Every record must carry complete metadata: source code, URL, reference period, date pulled, standalone/consolidated basis, and an actual/proxy/forecast label (forecast records must name the forecasting organization).
- Records from banned domains or missing a reference period: reject ingestion and log the reason.
- Before configuring a crawler against a government site, re-verify the URL one last time — the 2025 government restructuring broke many links (already flagged in sheet 04).
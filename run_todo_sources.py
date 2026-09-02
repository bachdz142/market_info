"""Phase 3, scoped: runs only the sources that have never had a real,
current-code LLM structuring pass — 39 of 47, validated with the user
2026-09-02 before running. Computed by checking data/signals.jsonl for a
genuine completed run (real signals, a real error, a real gate rejection,
or real token spend) and excluding the 2026-08-31 Groq-daily-quota-outage
artifacts (gate_passed=True, error=None, 0 signals, 0 tokens — that
predates agent/llm_fallback.py and isn't a real result).

Real cost/time: 39 sources, TOPIC_DELAY_SECONDS (30s) pacing between each,
several of them chunked/multi_pdf (many pieces, each its own paced LLM
call) — expect this to run a long while, possibly hours. Shows a live
tqdm progress bar (service.trigger()'s own) — run this directly in a
terminal, not piped/backgrounded, to see it update.

Usage: python run_todo_sources.py
"""

import service

TODO_SOURCE_IDS = [
    "acb_financial_statements",  # stale 2026-08-31 entry only, predates fallback chain
    "nso_data_and_statistics_official",
    "nso_gdp_key_indicators",
    "nso_vhlss_income",
    "nso_vhlss_expenditure",
    "chinhphu_legal_documents_official",
    "vnba_banking_news",
    "banking_review_journal",
    "finance_review_journal",
    "bidv_card_promotions",
    "bidv_personal_fee_schedule",
    "acb_promotions",
    "vpbank_news",
    "vpbank_fee_documents",
    "vcb_promotions",
    "acb_fee_schedule",
    "mbbank_fee_schedule",
    "mbbank_news",
    "vcb_fee_schedule",
    "sbv_circular_08_2026_tt_nhnn",
    "sbv_official_letter_4551_nhnn_cstt",
    "sbv_circular_21_2025_tt_nhnn",
    "decree_94_2025_nd_cp_fintech_sandbox",
    "resolution_57_nq_tw_digital_transformation",
    "resolution_110_2025_ubtvqh15_pit_deduction",
    "pit_law_109_2025_qh15",
    "decision_21_2025_qd_ttg_green_taxonomy",
    "sbv_circular_17_2022_tt_nhnn_environmental_risk",
    "ssi_banking_sector_report",
    "vcbs_banking_sector_report",
    "bsc_mbb_report",
    "decisionlab_bank_satisfaction_rankings",
    "qandme_online_banking_usage",
    "techcombank_mobile_release_notes",
    "vcb_digibank_release_notes",
    "bidv_smartbanking_release_notes",
    "mbbank_app_release_notes",
    "acb_one_release_notes",
    "vpbank_neo_release_notes",
]


def main() -> None:
    print(f"Running {len(TODO_SOURCE_IDS)} never-fully-run sources...")
    result = service.trigger(source_ids=",".join(TODO_SOURCE_IDS))

    topics = result["topics"]
    ok = [r for r in topics if r["gate_passed"] and not r["error"]]
    rejected = [r for r in topics if r["gate_passed"] is False]
    errored = [r for r in topics if r["error"]]

    print()
    print("===RUN COMPLETE===")
    print("run_id:", result["run_id"])
    print("run_seconds:", result["run_seconds"])
    print(f"{len(ok)} ok, {len(rejected)} gate-rejected, {len(errored)} errored, out of {len(topics)}")
    for r in rejected:
        print("REJECTED:", r["id"], "-", r["gate_reason"])
    for r in errored:
        print("ERRORED:", r["id"], "-", r["error"])


if __name__ == "__main__":
    main()

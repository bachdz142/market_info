import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SIGNALS_FILE = DATA_DIR / "signals.jsonl"
SIGNALS_CSV = DATA_DIR / "signals.csv"

CSV_HEADERS = [
    "triggered_at",
    "topic_id",
    "kind",
    "topic_seconds",
    "gate_passed",
    "gate_reason",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "error",
    "signal_type",
    "summary",
    "source_url",
    "observed_at",
    "confidence",
    "query",
    "generated_at",
]


def append_topic_jsonl(triggered_at: str, topic_result: dict) -> None:
    """Full-fidelity log: one JSON line per topic, written as soon as that topic
    finishes (success or failure) — so a crash mid-run doesn't lose earlier results."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SIGNALS_FILE.open("a") as f:
        f.write(json.dumps({"triggered_at": triggered_at, **topic_result}) + "\n")


def append_topic_csv(triggered_at: str, topic_result: dict) -> None:
    """Flattened log: one CSV row per signal (or one row per topic if it had no
    signals or errored), written as soon as that topic finishes."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    is_new_file = not SIGNALS_CSV.exists()

    with SIGNALS_CSV.open("a", newline="") as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(CSV_HEADERS)

        result = topic_result.get("result")
        signals = (result or {}).get("signals") or []
        usage = topic_result.get("token_usage") or {}
        common = [
            triggered_at,
            topic_result["id"],
            topic_result["kind"],
            topic_result.get("topic_seconds"),
            topic_result.get("gate_passed"),
            topic_result.get("gate_reason"),
            usage.get("input_tokens", ""),
            usage.get("output_tokens", ""),
            usage.get("total_tokens", ""),
            topic_result.get("error") or "",
        ]

        if not signals:
            writer.writerow(
                common
                + [
                    "", "", "", "", "",
                    (result or {}).get("query", ""),
                    (result or {}).get("generated_at", ""),
                ]
            )
            return

        for signal in signals:
            writer.writerow(
                common
                + [
                    signal.get("signal_type", ""),
                    signal.get("summary", ""),
                    signal.get("source_url", ""),
                    signal.get("observed_at", ""),
                    signal.get("confidence", ""),
                    result.get("query", ""),
                    result.get("generated_at", ""),
                ]
            )

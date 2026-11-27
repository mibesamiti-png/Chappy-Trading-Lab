"""CTL local-runner handoff pilot. Invented data only; no market files or network."""
import hashlib
import json
from pathlib import Path

JOB = "CTL-RUNNER-PILOT-001"
PROTOCOL = "synthetic-session-aggregation-v1"
HORIZONS = (1, 5, 15, 30)


def calculate(sessions):
    result = {}
    for h in HORIZONS:
        changes = [
            prices[i + h] - prices[i]
            for prices in sessions
            for i in range(0, len(prices) - h, h)
        ]
        result[str(h)] = {
            "windows": len(changes),
            "signed_sum": sum(changes),
            "absolute_sum": sum(abs(x) for x in changes),
        }
    return result


def main():
    # Two fictional sessions, with a large overnight price jump.
    # One rises by 1 each minute; the other is flat.
    sessions = [list(range(100, 161)), [10000] * 61]
    actual = calculate(sessions)
    expected = {
        str(h): {"windows": 120 // h, "signed_sum": 60, "absolute_sum": 60}
        for h in HORIZONS
    }
    status = "PASS" if actual == expected else "FAIL"
    print("--- SANITIZED PILOT REPORT ---")
    print(json.dumps({
        "job": JOB,
        "protocol": PROTOCOL,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "SYNTHETIC_ONLY",
        "status": status,
        "horizons": actual,
        "market_data": "NOT_READ",
        "holdout": "NOT_ACCESSED",
        "real_lease": "NOT_ACQUIRED",
    }, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Debug odds-api.io odds response for a known event_id and bookmaker names.

Run from project root:
    python jobs/debug_raw_odds_api_io.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.config import load_config  # noqa: E402


EVENT_ID = "61061635"  # Juventus Turin vs Hellas Verona

BOOKMAKERS_TO_TEST = [
    "William Hill",
    "Bet365",
    "bet365",
    "Pinnacle",
    "Unibet",
    "Bwin",
]


def main() -> int:
    config = load_config()

    if not config.odds_api_io_key:
        print("ERROR: ODDS_API_IO_KEY is missing")
        return 1

    url = f"{config.odds_api_io_base_url.rstrip('/')}/odds"
    output_dir = Path("data/debug_odds_api_io")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Testing odds-api.io bookmaker responses")
    print(f"URL: {url}")
    print(f"eventId: {EVENT_ID}")
    print()

    for bookmaker in BOOKMAKERS_TO_TEST:
        params = {
            "apiKey": config.odds_api_io_key,
            "eventId": EVENT_ID,
            "bookmakers": bookmaker,
        }

        print("=" * 80)
        print(f"BOOKMAKER: {bookmaker}")

        try:
            response = requests.get(
                url,
                params=params,
                timeout=config.request_timeout_s,
            )
        except requests.RequestException as exc:
            print(f"REQUEST ERROR: {exc}")
            continue

        print(f"HTTP status: {response.status_code}")

        safe_name = (
            bookmaker.lower()
            .replace(" ", "_")
            .replace(".", "")
            .replace("-", "_")
        )
        output_path = output_dir / f"event_{EVENT_ID}_{safe_name}.json"

        try:
            data = response.json()
        except ValueError:
            output_path.write_text(response.text, encoding="utf-8")
            print("Non-JSON response saved to:", output_path)
            print(response.text[:2000])
            continue

        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

        print(f"Saved response to: {output_path}")
        print("Preview:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
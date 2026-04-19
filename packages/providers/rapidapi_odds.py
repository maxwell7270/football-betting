import requests
from datetime import datetime
from packages.config import get_settings
from packages.models import OddsBundle, OddsQuote, Fixture
from packages.logging_utils import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RapidApiOddsProvider:
    source_name = "rapidapi"

    def __init__(self) -> None:
        self.api_key = settings.rapidapi_key
        self.host = settings.rapidapi_host_odds_feed or settings.rapidapi_host_pinnacle
        self.timeout = settings.request_timeout_ms / 1000

    def fetch_match_odds(self, fixture: Fixture, markets: list[str]) -> OddsBundle | None:
        if not self.host:
            return None

        quotes: list[OddsQuote] = []
        fetched_at = datetime.utcnow()

        url = f"https://{self.host}/odds"
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
        }

        params = {
            "home": fixture.home_team,
            "away": fixture.away_team,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            if response.status_code != 200:
                return None

            payload = response.json()

            for item in payload.get("data", []):
                bookmaker = item.get("bookmaker", "unknown")
                market = item.get("market")
                selection = item.get("selection")
                odds = item.get("odds")

                if not market or not selection or odds is None:
                    continue

                if market not in markets:
                    continue

                quotes.append(
                    OddsQuote(
                        fixture_id=fixture.fixture_id,
                        source=self.source_name,
                        bookmaker=bookmaker,
                        market=market,
                        selection=selection,
                        odds=float(odds),
                        fetched_at=fetched_at,
                        is_fallback=True,
                    )
                )
        except Exception as exc:
            logger.warning("RapidAPI fallback failed for fixture=%s: %s", fixture.fixture_id, exc)
            return None

        if not quotes:
            return None

        return OddsBundle(
            fixture_id=fixture.fixture_id,
            quotes=quotes,
            source_used=self.source_name,
        )
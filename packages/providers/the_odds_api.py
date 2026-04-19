import requests
from datetime import datetime
from packages.cache import build_cache_key, get_cached, set_cached
from packages.config import get_settings
from packages.models import OddsBundle, OddsQuote, Fixture
from packages.logging_utils import get_logger

logger = get_logger(__name__)
settings = get_settings()


class TheOddsApiProvider:
    source_name = "theoddsapi"

    def __init__(self) -> None:
        self.base_url = settings.the_odds_api_base_url
        self.api_key = settings.the_odds_api_key
        self.timeout = settings.request_timeout_ms / 1000

    def fetch_match_odds(self, fixture: Fixture, markets: list[str]) -> OddsBundle | None:
        all_quotes: list[OddsQuote] = []

        for market in markets:
            cache_key = build_cache_key(self.source_name, fixture.fixture_id, market)
            cached = get_cached(cache_key, settings.odds_cache_ttl_minutes)
            if cached:
                quotes = self._parse_quotes(fixture, cached, market)
                all_quotes.extend(quotes)
                continue

            logger.info("Fallback to The Odds API for fixture=%s market=%s", fixture.fixture_id, market)

            url = f"{self.base_url}/v4/sports/soccer/odds"
            params = {
                "apiKey": self.api_key,
                "regions": "eu",
                "markets": market,
                "oddsFormat": "decimal",
            }

            response = requests.get(url, params=params, timeout=self.timeout)
            if response.status_code != 200:
                logger.warning("The Odds API failed for fixture=%s market=%s", fixture.fixture_id, market)
                continue

            payload = response.json()
            set_cached(cache_key, payload)

            quotes = self._parse_quotes(fixture, payload, market)
            all_quotes.extend(quotes)

        if not all_quotes:
            return None

        return OddsBundle(
            fixture_id=fixture.fixture_id,
            quotes=all_quotes,
            source_used=self.source_name,
        )

    def _parse_quotes(self, fixture: Fixture, payload: list[dict], market: str) -> list[OddsQuote]:
        quotes: list[OddsQuote] = []
        fetched_at = datetime.utcnow()

        for event in payload:
            home = event.get("home_team")
            away = event.get("away_team")
            if fixture.home_team != home or fixture.away_team != away:
                continue

            for bookmaker_row in event.get("bookmakers", []):
                bookmaker = bookmaker_row.get("title", "unknown")
                for market_row in bookmaker_row.get("markets", []):
                    if market_row.get("key") != market:
                        continue

                    for outcome in market_row.get("outcomes", []):
                        name = outcome.get("name")
                        price = outcome.get("price")
                        if name is None or price is None:
                            continue

                        quotes.append(
                            OddsQuote(
                                fixture_id=fixture.fixture_id,
                                source=self.source_name,
                                bookmaker=bookmaker,
                                market=market,
                                selection=name,
                                odds=float(price),
                                fetched_at=fetched_at,
                                is_fallback=True,
                            )
                        )

        return quotes
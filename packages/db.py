from packages.logging_utils import get_logger

logger = get_logger(__name__)


def store_fixtures(fixtures):
    logger.info("Storing %s fixtures", len(fixtures))
    # TODO: INSERT ... ON CONFLICT DO UPDATE


def store_odds_bundles(bundles):
    count = sum(len(b.quotes) for b in bundles)
    logger.info("Storing %s bundles / %s odds quotes", len(bundles), count)
    # TODO: INSERT ... ON CONFLICT DO NOTHING / UPDATE


def export_daily_picks():
    logger.info("Exporting daily picks")
    # TODO
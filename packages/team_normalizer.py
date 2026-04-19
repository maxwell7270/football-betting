NORMALIZATION_MAP = {
    "Bayern Munich": "Bayern München",
    "Bayern Munchen": "Bayern München",
    "Man United": "Manchester United",
    "Man Utd": "Manchester United",
    "PSG": "Paris Saint-Germain",
}


def normalize_team_name(name: str) -> str:
    return NORMALIZATION_MAP.get(name.strip(), name.strip())
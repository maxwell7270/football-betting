# data_fetcher.py - 100% mit deinen Keys, ohne THE_ODDS_API
import requests
import pandas as pd
import sqlite3
import yaml
import os
from datetime import datetime, timedelta

class FootballDataFetcher:
    def __init__(self, config: dict):
        self.config = config
        self.api_football_headers = {
            'x-rapidapi-key': config['RAPIDAPI_KEY'],
            'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
            'x-apisports-key': config['API_FOOTBALL_KEY']
        }
        self.odds_api_io_headers = {
            'Authorization': f'Bearer {config["ODDS_API_IO_KEY"]}'
        }
    
    def fetch_fixtures_odds(self) -> pd.DataFrame:
        """API-FOOTBALL: Fixtures + Odds in einem Call"""
        all_data = []
        league_ids = list(self.config['LEAGUES'].keys())
        
        for league_id in league_ids:
            # Kommende 7 Tage
            url = "https://v3.football.api-sports.io/fixtures"
            params = {
                'league': league_id,
                'next': '14',  # 2 Wochen
                'timezone': self.config['TIMEZONE']
            }
            
            resp = requests.get(url, headers=self.api_football_headers, params=params)
            if resp.status_code == 200:
                fixtures = resp.json()['response']
                
                for fixture in fixtures:
                    # Odds für dieses Fixture holen
                    odds_url = "https://v3.football.api-sports.io/odds"
                    odds_params = {'fixture': fixture['fixture']['id']}
                    odds_resp = requests.get(odds_url, headers=self.api_football_headers, params=odds_params)
                    
                    home_odds = draw_odds = away_odds = ou_over = ou_under = None
                    if odds_resp.status_code == 200:
                        odds_data = odds_resp.json()['response']
                        if odds_data:
                            # Bet365 priorisieren
                            for odd in odds_data:
                                if 'Bet365' in odd['bookmaker']['name']:
                                    bets = odd['bookmakers'][0]['bets']
                                    for bet in bets:
                                        if bet['bet'] == 'Match Winner':
                                            home_odds = bet['values'][0]['odd']
                                            draw_odds = bet['values'][1]['odd']
                                            away_odds = bet['values'][2]['odd']
                                        elif bet['bet'] == 'Over/Under - 2.5':
                                            ou_over = bet['values'][0]['odd']
                                            ou_under = bet['values'][1]['odd']
                    
                    all_data.append({
                        'fixture_id': fixture['fixture']['id'],
                        'league_id': league_id,
                        'league': self.config['LEAGUES'][str(league_id)],
                        'datetime': fixture['fixture']['date'],
                        'home_team': fixture['teams']['home']['name'],
                        'away_team': fixture['teams']['away']['name'],
                        'home_odds': home_odds,
                        'draw_odds': draw_odds,
                        'away_odds': away_odds,
                        'ou25_over': ou_over,
                        'ou25_under': ou_under
                    })
        
        df = pd.DataFrame(all_data)
        conn = sqlite3.connect('data/football.db')
        df.to_sql('fixtures_odds', conn, if_exists='replace', index=False)
        conn.close()
        
        print(f"✅ {len(df)} Fixtures + Odds von API-FOOTBALL geladen")
        return df
    
    def fetch_historical(self, days_back: int = 365):
        """Historische Daten für Elo-Training"""
        url = "https://v3.football.api-sports.io/fixtures"
        params = {
            'last': str(days_back),
            'timezone': self.config['TIMEZONE']
        }
        # Vereinfacht - erweitere bei Bedarf
        print("📚 Historische Daten verfügbar (optional)")
    
    def full_update(self):
        """Tägliches komplettes Update"""
        os.makedirs('data', exist_ok=True)
        fixtures_df = self.fetch_fixtures_odds()
        self.fetch_historical()
        return fixtures_df

# Usage
if __name__ == "__main__":
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    fetcher = FootballDataFetcher(config)
    fetcher.full_update()
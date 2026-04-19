# main.py - Doppelklick ready
import sqlite3
import pandas as pd
import yaml
import os
import sys
from data_fetcher import FootballDataFetcher

# Einfaches Dummy-Modell (später dein Elo/Poisson)
def simple_prediction(home_odds, away_odds, league_strength=1.0):
    """Baseline: Erwartete Wahrscheinlichkeiten aus Odds"""
    total_prob = (1/home_odds + 1/away_odds + 0.25)  # +Draw implizit
    return {
        'p_home': (1/home_odds) / total_prob * league_strength,
        'p_away': (1/away_odds) / total_prob
    }

def main():
    print("=== ⚽ AUTO FOOTBALL BETTING MVP ===\n")
    
    # Config laden
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # 1. Vollautomatisches Update
    print("📡 Update Daten...")
    fetcher = FootballDataFetcher(config)
    fixtures_df = fetcher.full_update()
    
    # 2. Value Detection
    print("\n🎯 VALUE BETS (Edge > {:.1%})".format(config['MIN_EDGE']))
    signals = []
    
    conn = sqlite3.connect('data/football.db')
    df = pd.read_sql("SELECT * FROM fixtures_odds WHERE home_odds IS NOT NULL", conn)
    
    for _, row in df.iterrows():
        pred = simple_prediction(row['home_odds'], row['away_odds'])
        
        # Edge berechnen
        fair_home = 1 / pred['p_home']
        edge_home = (pred['p_home'] * row['home_odds']) - 1
        
        if edge_home > config['MIN_EDGE']:
            signals.append({
                f"{row['home_team'][:15]:<15} vs {row['away_team'][:15]:<15}",
                f"{edge_home:.1%}",
                f"{row['home_odds']:.2f}",
                f"{fair_home:.2f}"
            })
    
    # 3. Ausgabe
    if signals:
        for signal in signals:
            print(f"  💰 {signal[0]} | Edge: {signal[1]} | Odds: {signal[2]} (Fair: {signal[3]})")
    else:
        print("  😴 Keine Value Bets heute")
    
    print(f"\n📊 {len(df)} Spiele analysiert | {len(signals)} Signale")
    conn.close()

if __name__ == "__main__":
    main()
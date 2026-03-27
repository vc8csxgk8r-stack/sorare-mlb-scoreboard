"""
test_local.py — Lance en dehors de Docker pour vérifier que tout fonctionne.
Usage : python test_local.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__) + "/app")
os.environ["DB_PATH"] = "/tmp/test_sorare.db"

import datetime
import db
import mlb_fetcher
import sorare_scoring

print("=== 1. Init DB ===")
db.init_db()
print("OK")

print("\n=== 2. Recherche joueur (Shohei Ohtani) ===")
try:
    results = mlb_fetcher.search_player("Shohei Ohtani")
    for r in results[:3]:
        print(f"  {r['id']} | {r['name']} | {r['team']} | {r['position']}")
except Exception as e:
    print(f"ERREUR : {e}")

print("\n=== 3. Matchs hier ===")
yesterday = datetime.date.today() - datetime.timedelta(days=1)
try:
    ids = mlb_fetcher.get_game_ids_for_date(yesterday)
    print(f"  {len(ids)} matchs terminés le {yesterday}: {ids[:5]}")
except Exception as e:
    print(f"ERREUR : {e}")

print("\n=== 4. Test scoring hitter ===")
fake_hitter = {
    "role": "hitter", "singles": 1, "doubles": 1, "triples": 0,
    "home_runs": 1, "rbi": 3, "runs": 2, "stolen_bases": 1,
    "caught_stealing": 0, "walks_bat": 1, "strikeouts_bat": 1,
    "hit_by_pitch": 0, "sacrifice_fly": 0, "hits": 3,
}
s = sorare_scoring.compute_score(fake_hitter)
print(f"  Score : {s['total']}")
print(f"  Détail : {s['breakdown']}")

print("\n=== 5. Test scoring pitcher ===")
fake_pitcher = {
    "role": "pitcher", "innings_pitched": 7.0, "strikeouts": 9,
    "walks": 1, "hits_allowed": 4, "earned_runs": 1,
    "home_runs_allowed": 0, "wins": 1, "losses": 0,
    "saves": 0, "holds": 0, "blown_saves": 0,
    "complete_game": 0, "shutout": 0, "no_hitter": 0,
}
s = sorare_scoring.compute_score(fake_pitcher)
print(f"  Score : {s['total']}")
print(f"  Détail : {s['breakdown']}")

print("\n✅ Tous les tests passés.")

# ⚾ Sorare MLB Scoreboard — Version corrigée

Dashboard Streamlit calculant les **scores Sorare MLB** depuis l'API officielle MLB, sans login Sorare.

---

## 🐛 Bugs corrigés vs version originale

| Problème original | Correction apportée |
|---|---|
| API MLB : endpoints cassés / structure JSON changée | Réécriture complète du fetcher avec l'API v1 actuelle (`statsapi.mlb.com/api/v1`) |
| `MLB-StatsAPI` lib obsolète | Supprimée — appels HTTP directs avec `requests` |
| Crash au 1er démarrage si `/data` vide | `db.init_db()` crée la DB au démarrage, vérification `is_date_synced` avant fetch |
| Scores à 0 pour les pitchers | Détection rôle via `stats.pitching.inningsPitched` (non nul) avant batting |
| Parsing `inningsPitched` ("6.2" = 6⅔ manches) | Conversion correcte en float décimal (6 + 2/3 = 6.667) |
| Dépendances sans version → conflits | `requirements.txt` avec versions pinned et testées |
| Synchro bloquante (UI gelée) | Lock non-bloquant + callback de progression pour Streamlit |
| Timezone : matchs marqués "mauvais jour" | Container en `America/New_York`, filtre `abstractGameState=Final` |

---

## 🚀 Déploiement

### Portainer (recommandé)

1. **Portainer → Stacks → Add stack**
2. Colle le contenu de `docker-compose.yml`  
   *(ou utilise Git repository avec l'URL de ton repo)*
3. **Deploy the stack**
4. Accède à `http://ton-ip:8501`

### Ligne de commande

```bash
docker compose up -d --build
```

---

## 📖 Utilisation

### 1. Ajouter des joueurs (sidebar gauche)
- Tape le nom d'un joueur dans la barre de recherche
- Clique **＋** pour l'ajouter au roster
- Le rôle (Hitter/Pitcher) est détecté automatiquement

### 2. Synchroniser les données (onglet 🔄 Synchronisation)
- **Premier lancement** : va dans "Synchro des N derniers jours" et lance pour 7 jours
- Ensuite la **synchro automatique** tourne toutes les 15 min entre 13h et 04h UTC

### 3. Voir les scores (onglet 📊 Scores du jour)
- Sélectionne une date avec le sélecteur
- Clique sur un joueur pour voir le détail du scoring
- Le bouton **🔄 Synchro maintenant** force un re-fetch de la date affichée

### 4. Historique (onglet 📅 Historique)
- Tableau croisé Joueur × Date avec totaux et moyennes
- Graphe individuel par joueur

---

## 🧮 Barême Sorare MLB

### Hitters
| Action | Points |
|---|---|
| Single | +2 |
| Double | +5 |
| Triple | +8 |
| Home Run | +10 |
| RBI | +3 |
| Run | +3 |
| Stolen Base | +5 |
| Walk / HBP | +2 |
| Strikeout | -1 |

### Pitchers
| Action | Points |
|---|---|
| Inning Pitched | +3 |
| Strikeout | +2 |
| Walk | -1 |
| Hit Allowed | -0.5 |
| Earned Run | -2 |
| Hit Batsman | -1 |
| Win | +5 |
| Save | +10 |
| Hold | +5 |

---

## 🔧 Structure du projet

```
sorare-mlb/
├── app/
│   ├── main.py           # Interface Streamlit
│   ├── mlb_fetcher.py    # Appels API MLB officielle
│   ├── sorare_scoring.py # Calcul des scores Sorare
│   ├── sync.py           # Orchestration + scheduler
│   └── db.py             # Base SQLite locale
├── data/                 # Volume Docker (DB persistante)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## ⚙️ Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `DB_PATH` | `/data/sorare_mlb.db` | Chemin de la base SQLite |
| `TZ` | `America/New_York` | Timezone (important pour les dates) |

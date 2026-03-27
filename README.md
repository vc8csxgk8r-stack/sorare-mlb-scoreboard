# Sorare MLB Scoreboard

Dashboard Streamlit qui calcule les **scores Sorare MLB** à partir des données officielles MLB (aucun login Sorare requis).

### Fonctionnalités
- Calcul précis avec la matrice de scoring Sorare officielle (hitter + pitcher)
- Snapshot quotidien stable → tu vois toujours le score du **jour d’avant**
- Gros bouton pour synchro manuelle
- Synchro automatique toutes les **10 minutes** les jours où il y a des matchs MLB
- Gestion simple du roster dans l’interface

### Déploiement dans Portainer (depuis GitHub)
1. Portainer → **Stacks** → **Add stack**
2. Choisis **Git repository**
3. Mets l’URL de ton repo GitHub
4. Compose path : `docker-compose.yml`
5. Déploie

Le dashboard sera disponible sur `http://ton-ip:8501`

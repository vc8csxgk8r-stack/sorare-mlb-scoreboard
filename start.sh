#!/bin/bash
# start.sh — Lance Streamlit (8501) + FastAPI (8502) dans le même container

set -e

echo "🚀 Démarrage Sorare MLB Scoreboard..."

# FastAPI en arrière-plan
cd /app
python api.py &
API_PID=$!
echo "✅ API FastAPI démarrée (PID $API_PID) → port 8502"

# Streamlit au premier plan
streamlit run main.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false &
ST_PID=$!
echo "✅ Streamlit démarré (PID $ST_PID) → port 8501"

# Attendre que l'un des deux meure
wait -n $API_PID $ST_PID
echo "⚠️  Un process s'est arrêté, extinction..."
kill $API_PID $ST_PID 2>/dev/null

#!/bin/bash
# ─────────────────────────────────────────────────────────
#  CargoPulse — start everything with one command
#  Usage: ./start.sh
# ─────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

# Kill any leftover instances from a previous run
pkill -f "run_ais_background.py" 2>/dev/null && echo "⚠️  Stopped previous AIS fetcher." || true
pkill -f "streamlit run Home.py"  2>/dev/null && echo "⚠️  Stopped previous Streamlit." || true
sleep 1

echo ""
echo "🔌  Starting AIS background fetcher…"
python run_ais_background.py &
AIS_PID=$!
echo "    PID $AIS_PID — fetching live vessel data in background."

# Give the fetcher a head start so Streamlit's first render shows real data
echo "    Waiting 5 s for initial vessel data…"
sleep 5

echo ""
echo "🌐  Starting CargoPulse dashboard on http://localhost:8501"
echo "    Press Ctrl+C to stop both processes."
echo ""

# Run Streamlit in foreground; when it exits (Ctrl+C), clean up the fetcher
streamlit run Home.py --server.port 8501 || true

echo ""
echo "Shutting down AIS background fetcher (PID $AIS_PID)…"
kill "$AIS_PID" 2>/dev/null || true
echo "✅  CargoPulse stopped."

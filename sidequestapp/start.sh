#!/bin/bash
# Side Quest App - Start Script
echo "🗺️  Starting Side Quest App..."
echo ""

# Start backend
echo "⚔️  Starting Flask backend on https://sidequest-yz6z.onrender.com ..."
cd "$(dirname "$0")/backend"
python3 -m venv venv 2>/dev/null || true
source venv/bin/activate
pip install -r requirements.txt -q
python app.py &
BACKEND_PID=$!

echo "✅ Backend running (PID: $BACKEND_PID)"
echo ""
echo "🌐 To run the frontend, in a new terminal:"
echo "   cd frontend && npm install && npm start"
echo ""
echo "Press Ctrl+C to stop the backend."
wait $BACKEND_PID

const API = "https://sidequest-yz6z.onrender.com";

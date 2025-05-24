echo "Setting up environment...."
# Ensure we are in the correct directory if needed, though usually the script runs in the app root.
# cd /app # Or the appropriate path if your Dockerfile/Procfile sets a different working directory

echo "Dependencies installed during Docker build."

echo "Starting Bot...."
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 &
python3 bot.py

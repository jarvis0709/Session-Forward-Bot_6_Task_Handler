echo "Setting up environment...."
# Ensure we are in the correct directory if needed, though usually the script runs in the app root.
# cd /app # Or the appropriate path if your Dockerfile/Procfile sets a different working directory

echo "Installing dependencies...."
pip3 install -r requirements.txt

echo "Starting Bot...."
python3 bot.py

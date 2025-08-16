#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Configure ngrok authtoken from environment variable
if [ -n "$NGROK_AUTH_TOKEN" ]; then
  ngrok config add-authtoken $NGROK_AUTH_TOKEN
  echo "✅ ngrok authtoken configured."
else
  echo "⚠️ NGROK_AUTH_TOKEN not set. Using unauthenticated ngrok session."
fi

# Start ngrok in the background to expose port 8000
echo "Starting ngrok tunnel for port 8000..."
ngrok http 8000 --log=stdout &

# Wait a moment for ngrok to initialize its API
sleep 2

# Retrieve the public URL from the ngrok API
echo "Fetching ngrok public URL..."
PUBLIC_URL=""
for i in {1..10}; do
  PUBLIC_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | jq -r '.tunnels[] | select(.proto=="https") | .public_url')
  if [ -n "$PUBLIC_URL" ]; then
    break
  fi
  echo "Waiting for ngrok URL... (attempt $i)"
  sleep 2
done

if [ -z "$PUBLIC_URL" ]; then
  echo "❌ Error: Could not retrieve ngrok public URL after several attempts."
  exit 1
fi

# Export the URL for the application to use
export NGROK_URL=$PUBLIC_URL
echo "🌍 Public URL found: $NGROK_URL"
echo "NGROK_URL has been set as an environment variable."

# Execute the command passed to this script (e.g., starts the uvicorn server)
echo "Executing main application command..."
exec "$@"

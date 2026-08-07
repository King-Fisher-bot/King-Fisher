# King Fisher Bot — Fixed Webhook Version

This version does NOT delete the Telegram webhook when Render shuts down or spins down the free service.

## Environment Variables

BOT_TOKEN = your BotFather token
PUBLIC_URL = your current Render URL
WEBHOOK_SECRET = your own secret

Example:

PUBLIC_URL=https://king-fisher-0g8k.onrender.com

## Build Command

pip install -r requirements.txt

## Start Command

uvicorn bot:app --host 0.0.0.0 --port $PORT

Token is intentionally not included in this repository.

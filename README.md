# King Fisher Bot - Real Device Data Integration

## Features
- Real-time SMS monitoring from Android devices
- Real-time Call log monitoring from Android devices
- Secure webhook-based communication
- Telegram bot interface
- Multi-device support

## Architecture
1. **Android Device**: Runs `android_sender.py` via Termux
2. **Telegram Bot**: FastAPI server with webhook
3. **Communication**: HTTPS with secret token authentication

## Setup

### 1. Telegram Bot
1. Create bot via @BotFather
2. Set environment variables:
   - `BOT_TOKEN`: Your bot token
   - `PUBLIC_URL`: Your Render/Heroku URL
   - `WEBHOOK_SECRET`: Random secret string

### 2. Android Device
1. Install Termux (F-Droid version)
2. Install required packages:
   ```bash
   pkg update && pkg upgrade
   pkg install python termux-api termux-tools
   pip install requests

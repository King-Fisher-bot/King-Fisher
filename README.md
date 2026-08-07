# King Fisher Bot — Webhook Version

BotFather Token GitHub-এ রাখা হবে না।

Environment Variables:
- BOT_TOKEN = BotFather-এর নতুন Token
- PUBLIC_URL = deploy হওয়ার পর HTTPS service URL
- WEBHOOK_SECRET = একটি নিজের secret text

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
uvicorn bot:app --host 0.0.0.0 --port $PORT
```

Features:
- /start
- /items
- /restart
- /close
- /help
- /about
- Inline menu
- SMS placeholder
- CALL placeholder

SMS/Call অংশে ব্যক্তিগত তথ্য সংগ্রহ বা দেখানোর ব্যবস্থা নেই।

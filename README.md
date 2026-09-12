# PersonalBot

A Python Discord bot for AI chat, music, and fun commands.

## Features

- AI assistant with OpenAI
- Music playback from YouTube/search results
- Queue, pause, resume, skip, stop, and voice-channel controls
- Fun commands such as 8ball, coinflip, roll, choose, ship, and jokes
- Slash commands and selected prefix commands

## Setup

```bash
git clone https://github.com/shackdoww/personalbot.git
cd personalbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

Install FFmpeg on Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

For 24/7 hosting, copy `bot.service.example` to `/etc/systemd/system/personalbot.service`, adjust the username/path if needed, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now personalbot
sudo systemctl status personalbot
journalctl -u personalbot -f
```

## Discord setup

Create a bot in the Discord Developer Portal and invite it with the `bot` and `applications.commands` scopes. Enable the Message Content intent if prefix commands are needed.

Never commit `.env` or API keys.

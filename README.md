# bt-dl — Telegram Torrent Search Bot for Rutracker

> 🤖 A Telegram bot that searches torrents on **Rutracker.org**, lets you filter by forum, and downloads `.torrent` files directly to your watch directory (e.g., for Woodpecker or qBittorrent).

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20WSL-lightgrey)

## Features

- Full-text search on Rutracker
- Interactive forum filtering (e.g., "Movies → UHD Video")
- Download selected torrents directly to your filesystem
- Automatic integration with torrent clients via **watch directory**
- Clean, numbered inline buttons for easy selection
- No web UI needed — everything via Telegram

## Installation

Install directly from GitHub:
```bash
git clone https://github.com/AstraSerg/bt-dl.git
cd bt-dl; pip install -e .
```
## Configuration

- Create a .env file in your project directory
```bash
cp .env.example .env
```
- Fill in your credentials:
```asciidoc
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
RUTRACKER_LOGIN=your_rutracker_username
RUTRACKER_PASSWORD=your_rutracker_password
TORRENTS_DIR=/path/to/your/watch/folder
```

## Usage

- Start
```bash
bt-dl-bot
```
- In Telegram, send any search query:
```bash
мурзилка
```
- Choose a forum filter (🝖) or a torrent (🎬) from the list.
- The selected .torrent file is saved to TORRENTS_DIR.
- Configure Your torrent client (e.g., Deluge, qBittorrent) to auto-add it.

## Uninstall
```bash
pip uninstall -y bt-dl-bot
rm -r bt-dl/
rm -f ~/.local/bin/bt-dl-bot
pip cache purge
```

## Important Notes

- This bot requires a valid Rutracker account.
- Respect Rutracker’s rules and rate limits.
- Do not use with public/shared accounts.
- The bot does not bypass geo-blocks — run it from an unblocked location (e.g., VPS outside Russia).

## License
MIT 

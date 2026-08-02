# 🤖 @MakeLinkShortBot

A powerful URL shortener bot for Telegram with multiple service support.

## ✨ Features

- 🔗 Shorten any URL instantly
- 🌐 Support for 4+ shortening services
- 👤 User preferences saved
- 🎨 Clean interface with buttons
- 📊 Usage statistics
- ⚡ Fast & reliable

## 🚀 Quick Deploy on Railway

### 1. Get Bot Token
- Message @BotFather on Telegram
- Create new bot: `/newbot`
- Copy the token

### 2. Deploy
- Fork this repository
- Connect to Railway
- Set `TELEGRAM_TOKEN` environment variable
- Deploy!

## 🔧 Commands

- `/start` - Welcome
- `/help` - Help
- `/services` - List services
- `/service <name>` - Change service
- `/shorten <url>` - Shorten URL
- `/stats` - Statistics
- `/about` - About

## 📝 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_TOKEN` | ✅ Yes | Bot token from @BotFather |
| `BOT_NAME` | ❌ No | Bot display name |
| `BOT_OWNER_ID` | ❌ No | Your Telegram ID |
| `DEFAULT_SHORTENER` | ❌ No | Default service (tinyurl) |

## 🛠️ Tech Stack

- Python 3.13
- python-telegram-bot 20.7
- PyShorteners
- Railway

## 📄 License

MIT License

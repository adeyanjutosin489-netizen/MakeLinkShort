# @MakeLinkShortBot - Telegram URL Shortener Bot

A Telegram bot that shortens URLs using multiple services.

## Features

- ✅ Shorten any URL instantly
- ✅ Support for multiple shortening services:
  - TinyURL (default)
  - Clck.ru
  - Da.gd
  - Is.gd
- ✅ User preference storage for service selection
- ✅ Inline buttons for easy interaction
- ✅ Error handling and logging
- ✅ Command system for advanced usage

## Commands

- `/start` - Welcome message
- `/help` - Show help
- `/services` - List available shortening services
- `/service <name>` - Change preferred service
- `/shorten <url>` - Shorten specific URL
- `/stats` - Usage statistics (coming soon)

## Deployment

### Environment Variables

- `TELEGRAM_TOKEN` - Your bot token from @BotFather

### Deploy on Railway

1. Push this code to GitHub
2. Connect Railway to your GitHub repository
3. Set the `TELEGRAM_TOKEN` environment variable
4. Deploy!

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable
export TELEGRAM_TOKEN="your_bot_token"

# Run the bot
python main.py

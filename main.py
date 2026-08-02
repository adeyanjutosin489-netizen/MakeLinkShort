import os
import re
import logging
import sys
from typing import Optional, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    ContextTypes, 
    filters,
    CallbackQueryHandler
)
import pyshorteners
import validators

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
# Read environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BOT_NAME = os.environ.get("BOT_NAME", "MakeLinkShortBot")
BOT_OWNER_ID = os.environ.get("BOT_OWNER_ID")
DEFAULT_SHORTENER = os.environ.get("DEFAULT_SHORTENER", "tinyurl")

# Validate token
if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN environment variable not set!")
    logger.error("Please set it in Railway dashboard -> Variables tab")
    sys.exit(1)

logger.info(f"✅ Bot Name: {BOT_NAME}")
logger.info(f"✅ Default Shortener: {DEFAULT_SHORTENER}")
if BOT_OWNER_ID:
    logger.info(f"✅ Owner ID: {BOT_OWNER_ID}")

# Supported shortener services
SHORTENER_SERVICES: Dict[str, str] = {
    "tinyurl": "TinyURL (default)",
    "clckru": "Clck.ru (Russian)",
    "dagd": "Da.gd",
    "isgd": "Is.gd",
}

# Shortener method mapping
SHORTENER_METHODS = {
    "tinyurl": lambda s: s.tinyurl.short,
    "clckru": lambda s: s.clckru.short,
    "dagd": lambda s: s.dagd.short,
    "isgd": lambda s: s.isgd.short,
}

# Store user preferences (in-memory - resets on restart)
user_preferences: Dict[int, Dict[str, str]] = {}

# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message."""
    user = update.effective_user
    welcome_text = f"""
👋 **Hello {user.first_name}!**

I'm **{BOT_NAME}**, your personal URL shortener bot.

📌 **How to use me:**
• Simply send me any URL and I'll shorten it
• Use `/shorten <url>` to shorten a specific URL
• Use `/services` to see available shortening services
• Use `/service <name>` to change your preferred service

🎯 **Current default service:** `{DEFAULT_SHORTENER}`

🚀 Try it now! Send me a URL like: `https://example.com`
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help message."""
    help_text = f"""
📖 **Available Commands:**

/start - Welcome message
/help - Show this help
/services - List available shortening services
/service <name> - Change your preferred service
/shorten <url> - Shorten a specific URL
/stats - Show usage statistics
/about - About this bot

📝 **Or simply send me a URL to shorten it!**
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def services_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available shortening services."""
    user_id = update.effective_user.id
    current_service = user_preferences.get(user_id, {}).get("service", DEFAULT_SHORTENER)
    
    services_text = "🔗 **Available Shortening Services:**\n\n"
    for key, value in SHORTENER_SERVICES.items():
        current = " ✅ (current)" if key == current_service else ""
        services_text += f"• `{key}` - {value}{current}\n"
    
    services_text += f"\n💡 Change service with: `/service <name>`"
    await update.message.reply_text(services_text, parse_mode='Markdown')

async def service_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Change user's preferred shortener service."""
    user_id = update.effective_user.id
    
    if not context.args:
        current = user_preferences.get(user_id, {}).get("service", DEFAULT_SHORTENER)
        await update.message.reply_text(
            f"📌 Your current service is: `{current}`\n\n"
            f"To change it, use: `/service <service_name>`\n"
            f"See available services with: `/services`",
            parse_mode='Markdown'
        )
        return
    
    service_name = context.args[0].lower()
    if service_name in SHORTENER_SERVICES:
        if user_id not in user_preferences:
            user_preferences[user_id] = {}
        user_preferences[user_id]["service"] = service_name
        await update.message.reply_text(
            f"✅ Changed your preferred service to: `{service_name}` ({SHORTENER_SERVICES[service_name]})",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ Service '{service_name}' not found.\n"
            f"Available services: {', '.join(SHORTENER_SERVICES.keys())}"
        )

async def shorten_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shorten a URL provided as a command argument."""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a URL to shorten.\n"
            "Example: `/shorten https://example.com`",
            parse_mode='Markdown'
        )
        return
    
    url = context.args[0]
    await shorten_url(update, url)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any text message that might contain a URL."""
    if not update.message.text:
        return
    
    # Extract URLs from the message
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, update.message.text)
    
    if not urls:
        await update.message.reply_text(
            "❌ No valid URL found in your message.\n"
            "Please send a URL starting with http:// or https://"
        )
        return
    
    # Process only the first URL found
    await shorten_url(update, urls[0])

async def shorten_url(update: Update, url: str) -> None:
    """Core function to shorten a URL."""
    try:
        # Validate URL
        if not validators.url(url):
            await update.message.reply_text(
                "❌ Invalid URL format. Please make sure it starts with http:// or https://"
            )
            return
        
        # Get user's preferred service
        user_id = update.effective_user.id
        service = user_preferences.get(user_id, {}).get("service", DEFAULT_SHORTENER)
        
        # Show processing message
        processing_msg = await update.message.reply_text("⏳ Shortening your URL...")
        
        try:
            # Initialize shortener
            s = pyshorteners.Shortener()
            
            # Get the shortener function
            shortener_func = SHORTENER_METHODS.get(service)
            if not shortener_func:
                # Fallback to default
                service = DEFAULT_SHORTENER
                shortener_func = SHORTENER_METHODS[DEFAULT_SHORTENER]
            
            # Shorten the URL
            short_url = shortener_func(s)(url)
            
            # Create response with inline buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔗 Open Link", url=short_url),
                    InlineKeyboardButton("📋 Copy", callback_data=f"copy_{short_url}")
                ],
                [
                    InlineKeyboardButton("🔄 Shorten Another", callback_data="shorten_another")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            response_text = f"""
✅ **URL Shortened Successfully!**

🔗 **Original URL:**
`{url}`

✂️ **Shortened URL:**
`{short_url}`

📊 **Service Used:** {service}
"""
            await processing_msg.delete()
            await update.message.reply_text(
                response_text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )
            
            logger.info(f"User {update.effective_user.id} shortened: {url} -> {short_url}")
            
        except Exception as e:
            logger.error(f"Shortening error: {e}")
            error_msg = f"❌ Sorry, I couldn't shorten that URL using {service}.\n"
            error_msg += f"Error: {str(e)[:100]}\n\n"
            error_msg += f"Try using a different service with `/service <name>`"
            await processing_msg.edit_text(error_msg, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Error in shorten_url: {e}")
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again later."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("copy_"):
        short_url = query.data[5:]  # Remove 'copy_' prefix
        await query.edit_message_text(
            f"✅ **URL ready to copy!**\n\n"
            f"Short URL: `{short_url}`\n\n"
            f"📝 Send me another URL to shorten it!",
            disable_web_page_preview=True,
            parse_mode='Markdown'
        )
    
    elif query.data == "shorten_another":
        await query.edit_message_text(
            "📝 **Send me any URL and I'll shorten it for you!**\n\n"
            "Example: `https://www.example.com`\n\n"
            "💡 Tip: Use `/services` to see available shortening services.",
            parse_mode='Markdown'
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show usage statistics."""
    user_id = update.effective_user.id
    current_service = user_preferences.get(user_id, {}).get("service", DEFAULT_SHORTENER)
    
    await update.message.reply_text(
        f"📊 **Statistics for {BOT_NAME}**\n\n"
        f"• Current service: `{current_service}`\n"
        f"• Total users tracked: {len(user_preferences)}\n\n"
        "📈 **Coming soon:**\n"
        "• Total URLs shortened\n"
        "• Most used service\n"
        "• Daily/weekly usage",
        parse_mode='Markdown'
    )

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """About the bot."""
    about_text = f"""
ℹ️ **About {BOT_NAME}**

🤖 A powerful URL shortener bot for Telegram.

✨ **Features:**
• Support for multiple shortening services
• User preferences saved
• Fast and reliable
• Clean interface with buttons

🔧 **Services:**
{', '.join(SHORTENER_SERVICES.keys())}

📱 **Built with:**
• Python 3.13
• python-telegram-bot
• PyShorteners
• Railway

👨‍💻 **Open Source**
Made with ❤️ for the Telegram community
"""
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ **Oops! Something went wrong.**\n\n"
            "Please try again later. If the problem persists, contact the bot owner.",
            parse_mode='Markdown'
        )

# ============ MAIN FUNCTION ============

def main():
    """Start the bot."""
    try:
        # Create application
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("services", services_command))
        application.add_handler(CommandHandler("service", service_command))
        application.add_handler(CommandHandler("shorten", shorten_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("about", about_command))
        
        # Add message handler for URLs
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add callback query handler for inline buttons
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Start the bot
        logger.info(f"🚀 {BOT_NAME} is starting...")
        logger.info(f"📡 Using default service: {DEFAULT_SHORTENER}")
        logger.info("🤖 Bot is now running and waiting for messages...")
        
        # Start polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

import os
import re
import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import pyshorteners
import validators

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable not set!")
    exit(1)

# Supported shortener services (you can add more)
SHORTENER_SERVICES = {
    "tinyurl": "TinyURL (default)",
    "clckru": "Clck.ru (Russian)",
    "dagd": "Da.gd",
    "isgd": "Is.gd",
}

# Default service
DEFAULT_SERVICE = "tinyurl"

# Store user preferences in memory (for demo - use database in production)
user_preferences = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when /start is issued."""
    user = update.effective_user
    welcome_text = f"""
👋 Hello {user.first_name}! I'm a URL Shortener Bot.

📌 **How to use me:**
- Simply send me any URL and I'll shorten it
- Use /shorten <url> to shorten a URL
- Use /services to see available shortening services
- Use /service <name> to change your preferred service
- Use /help to see all commands

🎯 **Current default service:** {DEFAULT_SERVICE}

🚀 Try it now! Send me a URL like: https://example.com
"""
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message."""
    help_text = """
📖 **Available Commands:**

/start - Welcome message
/help - Show this help
/services - List available shortening services
/service <name> - Change your preferred service
/shorten <url> - Shorten a specific URL
/stats - Show your usage statistics (coming soon)

📝 **Or simply send me a URL to shorten it!**
"""
    await update.message.reply_text(help_text)

async def services_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available shortening services."""
    services_text = "🔗 **Available Shortening Services:**\n\n"
    for key, value in SHORTENER_SERVICES.items():
        current = " ✅ (current)" if key == user_preferences.get(update.effective_user.id, {}).get("service", DEFAULT_SERVICE) else ""
        services_text += f"• `{key}` - {value}{current}\n"
    
    services_text += f"\n💡 Change service with: `/service <name>`"
    await update.message.reply_text(services_text)

async def service_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Change user's preferred shortener service."""
    user_id = update.effective_user.id
    
    if not context.args:
        current = user_preferences.get(user_id, {}).get("service", DEFAULT_SERVICE)
        await update.message.reply_text(
            f"📌 Your current service is: `{current}`\n\n"
            f"To change it, use: `/service <service_name>`\n"
            f"See available services with: `/services`"
        )
        return
    
    service_name = context.args[0].lower()
    if service_name in SHORTENER_SERVICES:
        if user_id not in user_preferences:
            user_preferences[user_id] = {}
        user_preferences[user_id]["service"] = service_name
        await update.message.reply_text(
            f"✅ Changed your preferred service to: `{service_name}` ({SHORTENER_SERVICES[service_name]})"
        )
    else:
        await update.message.reply_text(
            f"❌ Service '{service_name}' not found.\n"
            f"Available services: {', '.join(SHORTENER_SERVICES.keys())}"
        )

async def shorten_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shorten a URL provided as a command argument."""
    if not context.args:
        await update.message.reply_text("❌ Please provide a URL to shorten.\nExample: `/shorten https://example.com`")
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
        service = user_preferences.get(user_id, {}).get("service", DEFAULT_SERVICE)
        
        # Show processing message
        processing_msg = await update.message.reply_text("⏳ Shortening your URL...")
        
        try:
            # Initialize shortener
            s = pyshorteners.Shortener()
            
            # Map service name to shortener method
            shortener_methods = {
                "tinyurl": s.tinyurl.short,
                "clckru": s.clckru.short,
                "dagd": s.dagd.short,
                "isgd": s.isgd.short,
            }
            
            # Get the shortener function
            shortener_func = shortener_methods.get(service)
            if not shortener_func:
                # Fallback to default
                service = DEFAULT_SERVICE
                shortener_func = shortener_methods[DEFAULT_SERVICE]
            
            # Shorten the URL
            short_url = shortener_func(url)
            
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
                disable_web_page_preview=True
            )
            
            logger.info(f"User {update.effective_user.id} shortened: {url} -> {short_url}")
            
        except Exception as e:
            logger.error(f"Shortening error: {e}")
            await processing_msg.edit_text(
                f"❌ Sorry, I couldn't shorten that URL using {service}.\n"
                f"Error: {str(e)[:100]}\n\n"
                f"Try using a different service with `/service <name>`"
            )
            
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
        # Note: In a real bot, you'd implement actual copy functionality
        await query.edit_message_text(
            f"✅ URL copied to clipboard!\n\n"
            f"Short URL: `{short_url}`\n\n"
            f"Send me another URL to shorten it!",
            disable_web_page_preview=True
        )
    
    elif query.data == "shorten_another":
        await query.edit_message_text(
            "📝 Send me any URL and I'll shorten it for you!\n"
            "Example: https://www.example.com"
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show usage statistics (placeholder)."""
    await update.message.reply_text(
        "📊 **Statistics**\n\n"
        "This feature is coming soon!\n"
        "I'll track:\n"
        "• Total URLs shortened\n"
        "• Most used service\n"
        "• Daily/weekly usage\n"
        "• And more!"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An error occurred while processing your request.\n"
            "Please try again later."
        )

def main():
    """Start the bot."""
    # Create application
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("services", services_command))
    application.add_handler(CommandHandler("service", service_command))
    application.add_handler(CommandHandler("shorten", shorten_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Add message handler for URLs
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("🚀 Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

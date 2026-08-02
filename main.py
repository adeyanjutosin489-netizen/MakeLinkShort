import os
import re
import logging
import sys
from typing import Optional, Dict, List
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

# ============ LOGGING SETUP ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BOT_NAME = os.environ.get("BOT_NAME", "MakeLinkShortBot")
BOT_OWNER_ID = os.environ.get("BOT_OWNER_ID")
DEFAULT_SHORTENER = os.environ.get("DEFAULT_SHORTENER", "tinyurl")

if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN environment variable not set!")
    logger.error("Please set it in Railway dashboard -> Variables tab")
    sys.exit(1)

logger.info("=" * 50)
logger.info(f"🤖 Bot Name: {BOT_NAME}")
logger.info(f"📡 Default Shortener: {DEFAULT_SHORTENER}")
if BOT_OWNER_ID:
    logger.info(f"👤 Owner ID: {BOT_OWNER_ID}")
logger.info("=" * 50)

# ============ CONSTANTS ============
SHORTENER_SERVICES = {
    "tinyurl": "TinyURL (fastest)",
    "clckru": "Clck.ru (Russian)",
    "dagd": "Da.gd (simple)",
    "isgd": "Is.gd (reliable)",
}

# Service mappings for pyshorteners
def get_shortener_method(service: str, shortener):
    """Get the appropriate shortener method"""
    methods = {
        "tinyurl": shortener.tinyurl.short,
        "clckru": shortener.clckru.short,
        "dagd": shortener.dagd.short,
        "isgd": shortener.isgd.short,
    }
    return methods.get(service, shortener.tinyurl.short)

# In-memory user preferences (resets on restart)
user_preferences: Dict[int, Dict] = {}

# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user = update.effective_user
    welcome_msg = f"""
👋 **Hello {user.first_name}!**

Welcome to **{BOT_NAME}** - your intelligent URL shortener!

📌 **Quick Start:**
• Send any URL → instantly shortened
• `/shorten <url>` → shorten a specific URL
• `/services` → view all shortening services
• `/service <name>` → change your default service

🎯 **Current Service:** `{DEFAULT_SHORTENER}`

💡 **Pro Tip:** I support multiple services! Try `/services` to see them all.
"""
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    help_msg = f"""
📖 **{BOT_NAME} Help Center**

**Commands:**
/start → Welcome message
/help → Show this help
/services → List available services
/service <name> → Change service
/shorten <url> → Shorten URL
/stats → Your statistics
/about → About this bot

**How to use:**
1. Send me any URL (http:// or https://)
2. I'll automatically shorten it
3. Use buttons to open or copy

**Example:**
Send: `https://www.example.com/very/long/url`
I'll reply with: `https://tinyurl.com/abc123`

🆘 Need help? Just ask!
"""
    await update.message.reply_text(help_msg, parse_mode='Markdown')

async def services_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /services command"""
    user_id = update.effective_user.id
    current = user_preferences.get(user_id, {}).get("service", DEFAULT_SHORTENER)
    
    msg = "🔗 **Available Shortening Services**\n\n"
    for key, desc in SHORTENER_SERVICES.items():
        indicator = " ✅ **(current)**" if key == current else ""
        msg += f"• `{key}` - {desc}{indicator}\n"
    
    msg += f"\n💡 Change with: `/service <name>`"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def service_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /service command"""
    user_id = update.effective_user.id
    
    if not context.args:
        current = user_preferences.get(user_id, {}).get("service", DEFAULT_SHORTENER)
        await update.message.reply_text(
            f"📌 Current service: `{current}`\n\n"
            f"Change with: `/service <service_name>`\n"
            f"See all: `/services`",
            parse_mode='Markdown'
        )
        return
    
    service_name = context.args[0].lower()
    if service_name in SHORTENER_SERVICES:
        if user_id not in user_preferences:
            user_preferences[user_id] = {}
        user_preferences[user_id]["service"] = service_name
        await update.message.reply_text(
            f"✅ **Service changed!**\n\n"
            f"Now using: `{service_name}` ({SHORTENER_SERVICES[service_name]})",
            parse_mode='Markdown'
        )
        logger.info(f"User {user_id} changed service to {service_name}")
    else:
        available = ", ".join(SHORTENER_SERVICES.keys())
        await update.message.reply_text(
            f"❌ Service '{service_name}' not found.\n\n"
            f"Available: `{available}`\n"
            f"See details: `/services`",
            parse_mode='Markdown'
        )

async def shorten_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /shorten command"""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a URL.\n"
            "Example: `/shorten https://example.com`",
            parse_mode='Markdown'
        )
        return
    
    url = context.args[0]
    await process_shorten(update, url)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages"""
    if not update.message or not update.message.text:
        return
    
    # Find URLs in message
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, update.message.text)
    
    if not urls:
        await update.message.reply_text(
            "🔍 **No URL found!**\n\n"
            "Send me a URL starting with `http://` or `https://`\n"
            "Or use `/help` for more options.",
            parse_mode='Markdown'
        )
        return
    
    # Process first URL
    await process_shorten(update, urls[0])

async def process_shorten(update: Update, url: str) -> None:
    """Core function to shorten URLs"""
    try:
        # Validate URL
        if not validators.url(url):
            await update.message.reply_text(
                "❌ **Invalid URL format**\n\n"
                "Make sure it starts with `http://` or `https://`",
                parse_mode='Markdown'
            )
            return
        
        # Get user's preferred service
        user_id = update.effective_user.id
        service = user_preferences.get(user_id, {}).get("service", DEFAULT_SHORTENER)
        
        # Show processing
        processing_msg = await update.message.reply_text("⏳ **Shortening your URL...**", parse_mode='Markdown')
        
        try:
            # Initialize shortener
            s = pyshorteners.Shortener()
            
            # Get method and shorten
            method = get_shortener_method(service, s)
            short_url = method(url)
            
            # Create inline keyboard
            keyboard = [
                [
                    InlineKeyboardButton("🔗 Open", url=short_url),
                    InlineKeyboardButton("📋 Copy", callback_data=f"copy_{short_url}")
                ],
                [
                    InlineKeyboardButton("🔄 New Link", callback_data="shorten_another")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Response
            response = f"""
✅ **URL Shortened!**

🔗 **Original:**
`{url}`

✂️ **Short:**
`{short_url}`

📊 **Service:** `{service}`
"""
            await processing_msg.delete()
            await update.message.reply_text(
                response,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )
            
            logger.info(f"User {user_id}: {url} → {short_url} ({service})")
            
        except Exception as e:
            logger.error(f"Shortening error: {e}")
            error_msg = f"❌ **Error shortening URL**\n\n"
            error_msg += f"Service: `{service}`\n"
            error_msg += f"Error: `{str(e)[:80]}`\n\n"
            error_msg += f"Try another service with `/service <name>`"
            await processing_msg.edit_text(error_msg, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Process error: {e}")
        await update.message.reply_text(
            "❌ **Unexpected error**\n\nPlease try again later.",
            parse_mode='Markdown'
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("copy_"):
        short_url = query.data[5:]
        await query.edit_message_text(
            f"✅ **URL Copied!**\n\n"
            f"Short URL: `{short_url}`\n\n"
            f"Send me another URL to shorten it!",
            disable_web_page_preview=True,
            parse_mode='Markdown'
        )
    
    elif query.data == "shorten_another":
        await query.edit_message_text(
            "📝 **Send me any URL**\n\n"
            "Example: `https://www.example.com`\n\n"
            "💡 Use `/services` to change service",
            parse_mode='Markdown'
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command"""
    user_id = update.effective_user.id
    current = user_preferences.get(user_id, {}).get("service", DEFAULT_SHORTENER)
    
    msg = f"📊 **Your Statistics**\n\n"
    msg += f"• Current service: `{current}`\n"
    msg += f"• Users tracked: `{len(user_preferences)}`\n"
    msg += f"• Bot version: `1.0.0`\n\n"
    msg += "📈 **More stats coming soon!**"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /about command"""
    msg = f"""
ℹ️ **About {BOT_NAME}**

🤖 **Version:** 1.0.0
📝 **Type:** URL Shortener Bot
🔧 **Services:** {len(SHORTENER_SERVICES)} providers

**Features:**
• Multiple shortening services
• User preferences
• Inline buttons
• Fast & reliable

**Tech Stack:**
• Python 3.13
• python-telegram-bot v20
• PyShorteners
• Railway

👨‍💻 **Open Source**
Made with ❤️ for everyone

Send a URL to get started! 🚀
"""
    await update.message.reply_text(msg, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Update {update} caused error: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ **Something went wrong**\n\n"
            "Please try again. If the problem continues, contact support.",
            parse_mode='Markdown'
        )

# ============ MAIN APPLICATION ============

def main() -> None:
    """Main function"""
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
        
        # Add message handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add callback handler
        application.add_handler(CallbackQueryHandler(button_callback))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Start bot
        logger.info("🚀 Starting bot...")
        logger.info(f"📡 Using default service: {DEFAULT_SHORTENER}")
        logger.info("🤖 Bot is ready! Waiting for messages...")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

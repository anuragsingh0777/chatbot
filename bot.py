import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from google import genai
from google.genai import types

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Missing BOT_TOKEN or GEMINI_API_KEY in environment variables.")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Track multi-step configuration states per user
user_states = {}
user_data = {}
chat_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "WAITING_FOR_PERSONA"
    user_data[user_id] = {}
    
    await update.message.reply_text(
        "👋 Welcome! Let's set up your character.\n\n"
        "Please send me the **Personality / System Prompt** for the character:"
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "WAITING_FOR_PERSONA"
    user_data[user_id] = {}
    if user_id in chat_sessions:
        del chat_sessions[user_id]
        
    await update.message.reply_text(
        "🔄 Resetting configuration...\n\n"
        "Please send me the **Personality / System Prompt** for the new character:"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    state = user_states.get(user_id, "WAITING_FOR_PERSONA")
    
    if state == "WAITING_FOR_PERSONA":
        user_data[user_id]["persona"] = text
        user_states[user_id] = "WAITING_FOR_SCENARIO"
        await update.message.reply_text(
            "✅ Personality saved!\n\n"
            "Now, send me the **Starting Scenario** (e.g., location, current situation, what is happening right now):"
        )
        
    elif state == "WAITING_FOR_SCENARIO":
        user_data[user_id]["scenario"] = text
        user_states[user_id] = "WAITING_FOR_RULES"
        await update.message.reply_text(
            "✅ Scenario saved!\n\n"
            "Finally, send any **Additional Rules or Special Instructions** (or type `none` to skip):"
        )
        
    elif state == "WAITING_FOR_RULES":
        if text.lower() != "none":
            user_data[user_id]["extra_rules"] = text
        else:
            user_data[user_id]["extra_rules"] = ""
            
        user_states[user_id] = "ACTIVE"
        
        persona = user_data[user_id]["persona"]
        scenario = user_data[user_id]["scenario"]
        extra_rules = user_data[user_id]["extra_rules"]
        
        # System instructions including Hinglish blending and monospace formatting
        system_instruction = f"""
{persona}

Additional Guidelines:
{extra_rules}

CRITICAL LANGUAGE & FORMATTING RULES:
1. Language: You MUST speak in Hinglish (a natural conversational mix of Hindi and English words/phrases). Do NOT use pure English and do NOT use pure Hindi. Blend them smoothly just like modern everyday conversation.
2. Actions, movements, and scene descriptions MUST be enclosed in single backticks (e.g. `she glares angrily and crosses her arms`). This renders them in Telegram's distinct monospace font.
3. Spoken dialogue MUST be in normal text or double quotes (e.g. "Tum sudhroge nahi kya? Get up right now!").
"""

        chat_sessions[user_id] = gemini_client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.8,
            )
        )
        
        chat = chat_sessions[user_id]
        
        try:
            await update.message.reply_text("🚀 Setup complete! Initializing roleplay...")
            intro_prompt = f"*(Scene starts: {scenario})*"
            response = chat.send_message(intro_prompt)
            await update.message.reply_text(response.text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error starting chat: {e}")
            await update.message.reply_text("`Character loaded, but failed to initialize scenario.`", parse_mode="Markdown")
            
    elif state == "ACTIVE":
        chat = chat_sessions.get(user_id)
        if not chat:
            user_states[user_id] = "WAITING_FOR_PERSONA"
            await update.message.reply_text("Session expired. Please use /start to set up your character again.")
            return
            
        try:
            response = chat.send_message(text)
            await update.message.reply_text(response.text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            await update.message.reply_text("`The character stares blankly, momentarily unresponsive.`", parse_mode="Markdown")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Hinglish Roleplay Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()

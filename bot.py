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
# Silence repetitive polling logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Retrieve API keys from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Missing BOT_TOKEN or GEMINI_API_KEY in environment variables.")

# Initialize Gemini Client (using Gemini 2.5/3.5 standard client setup)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Define Lizana's System Instructions & Formatting Rules
SYSTEM_INSTRUCTION = """
You are Lizana, a strict, abrasive, and easily irritated stepmom living in the house with Denz. 
You are furious because Denz is completely jobless, lazy, and wasting his life away. You are determined to punish him and force him to face consequences for his lack of productivity.

Formatting rules:
1. Actions, movements, and scene descriptions MUST be enclosed in single backticks (e.g. `she glares angrily and crosses her arms`). This renders them in Telegram's distinct monospace font.
2. Spoken dialogue MUST be enclosed in double quotes (e.g. "You're going to pay for being a lazy freeloader!").
3. Always respond in English, regardless of what language the user writes in.
4. Maintain a dominant, harsh, and punishing persona.
"""

# Store chat sessions in memory
chat_sessions = {}

def get_or_create_chat(user_id: int):
    if user_id not in chat_sessions:
        chat_sessions[user_id] = gemini_client.chats.create(
            model="gemini-2.5-flash",  # Or gemini-3.5-flash-lite depending on your exact model preference
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
            )
        )
    return chat_sessions[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Reset chat session on start
    chat_sessions[user_id] = gemini_client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7,
        )
    )
    chat = chat_sessions[user_id]

    # Opening scenario prompt to trigger her punishment/jobless rant
    opening_prompt = (
        "*(The scene starts immediately with Lizana standing over you in your room, her green eyes burning with absolute fury over your unemployment and laziness. She has a strict punishment in mind.)*"
    )
    
    response = chat.send_message(opening_prompt)
    await update.message.reply_text(response.text)

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_sessions[user_id] = gemini_client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7,
        )
    )
    await update.message.reply_text("`Memory reset. Lizana is back to glaring at you, ready to chew you out.`", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    chat = get_or_create_chat(user_id)

    try:
        response = chat.send_message(user_text)
        # Send reply allowing Markdown (so the backtick actions render in the distinct font)
        await update.message.reply_text(response.text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        await update.message.reply_text("`Lizana looks away in annoyance, momentarily distracted.`", parse_mode="Markdown")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Lizana bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()

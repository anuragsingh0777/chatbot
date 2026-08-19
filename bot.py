import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from google import genai
from google.genai import types

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Retrieve API keys from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable missing!")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable missing!")

# Initialize Gemini Client globally
client = genai.Client(api_key=GEMINI_API_KEY)

# In-memory session store (user_id -> session_data)
user_sessions = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Initialize empty session waiting for persona
    user_sessions[user_id] = {
        "step": "persona",
        "persona": "",
        "scenario": "",
        "rules": (
            "1. Language: MUST speak in Hinglish (smooth mix of Hindi and English).\n"
            "2. Actions, movements, and scene descriptions MUST be enclosed in single backticks (e.g. `she adjusts her glasses`).\n"
            "3. Spoken dialogue in normal text or double quotes.\n"
            "4. Maintain character immersion strictly at all times."
        ),
        "user_name": update.effective_user.first_name or "Student",
        "chat_session": None,
    }

    await update.message.reply_text(
        "👋 **Welcome to the Interactive Roleplay Bot Setup!**\n\n"
        "Step 1: Send the **Character Persona** description.\n"
        "(e.g., A strict, intimidating, yet playfully seductive university professor...)"
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    await update.message.reply_text(
        "🔄 Session reset successfully. Type /start to begin a new setup."
    )


async def initialize_active_session(update: Update, session: dict):
    global client
    
    system_instruction = (
        f"[Character Persona]\n{session['persona']}\n\n"
        f"[Starting Scenario]\n{session['scenario']}\n\n"
        f"[Additional Rules & Guidelines]\n{session['rules']}\n\n"
        f"[User Information]\nUser's Name: {session['user_name']}\n\n"
        "[CRITICAL FORMATTING & SAFETY RULES]\n"
        "1. Language: MUST speak in Hinglish (smooth mix of Hindi and English) unless specified otherwise.\n"
        "2. Actions, movements, and scene descriptions MUST be enclosed in single backticks (e.g. `she smiles`).\n"
        "3. Spoken dialogue in normal text or double quotes.\n"
        "4. Never break character, never output blank responses, and always keep descriptions vivid and immersive."
    )

    try:
        session["chat_session"] = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.85,
                safety_settings=[
                    {
                        "category": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        "threshold": types.HarmBlockThreshold.BLOCK_NONE,
                    },
                    {
                        "category": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        "threshold": types.HarmBlockThreshold.BLOCK_NONE,
                    },
                    {
                        "category": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        "threshold": types.HarmBlockThreshold.BLOCK_NONE,
                    },
                    {
                        "category": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        "threshold": types.HarmBlockThreshold.BLOCK_NONE,
                    },
                ],
            ),
        )
    except Exception as e:
        logger.error(f"Failed to create chat session: {e}")
        await update.message.reply_text(f"⚠️ Error creating chat session: {e}")
        return

    session["step"] = "active"
    await update.message.reply_text(
        "🎉 **Setup Complete! Roleplay is now ACTIVE.**\n"
        "Generating opening sequence..."
    )

    try:
        initial_prompt = (
            f"Begin the roleplay scenario immediately based on the starting scenario. "
            f"Address the user as {session['user_name']} and establish the opening atmosphere."
        )
        response = session["chat_session"].send_message(initial_prompt)
        if response and response.text:
            await update.message.reply_text(response.text)
        else:
            await update.message.reply_text(
                "`She watches you intently, waiting for your first move...`"
            )
    except Exception as e:
        logger.error(f"Error generating opening response: {e}")
        await update.message.reply_text(
            "Session initialized! Send your first message to begin."
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_sessions:
        await update.message.reply_text("⚠️ No active setup found. Please type /start to begin.")
        return

    session = user_sessions[user_id]
    step = session.get("step")

    # Step 1: Taking Persona
    if step == "persona":
        session["persona"] = text
        session["step"] = "scenario"
        await update.message.reply_text(
            "✅ **Persona Saved!**\n\n"
            "Step 2: Send the **Starting Scenario**.\n"
            "(e.g., Late evening in a quiet university building inside a private office...)"
        )
        return

    # Step 2: Taking Scenario
    elif step == "scenario":
        session["scenario"] = text
        session["step"] = "name_input"
        await update.message.reply_text(
            "✅ **Scenario Saved!**\n\n"
            "Step 3: What is **your name** for the story? (e.g. Anurag)\n"
            "Type your name and send it."
        )
        return

    # Step 3: Taking User Name and Launching Session
    elif step == "name_input":
        session["user_name"] = text
        await initialize_active_session(update, session)
        return

    # Active Chat Mode
    chat = session.get("chat_session")
    if not chat:
        await update.message.reply_text("⚠️ Session error detected. Please type /reset to start over.")
        return

    try:
        response = chat.send_message(text)
        if response and response.text:
            await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("`She raises an eyebrow, waiting for you to elaborate...`")
    except Exception as e:
        logger.error(f"Error during chat: {e}")
        await update.message.reply_text(f"⚠️ An error occurred: {e}\nPlease type /reset to restart.")


def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logger.info("Bot is starting up...")
    application.run_polling()


if __name__ == "__main__":
    main()

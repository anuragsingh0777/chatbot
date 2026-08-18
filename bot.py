import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from google import genai
from google.genai import types

# Enable main logging, but silence noisy HTTP request logs from httpx
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
MODEL_ID = "gemini-3.1-flash-lite"

# Track multi-step configuration states and conversation history per user
user_states = {}
user_data = {}
USER_MEMORIES = {}
SYSTEM_PROMPTS = {}

# Universal safety settings to completely disable blocking for NSFW/Roleplay content
SAFETY_CONFIG = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "WAITING_FOR_PERSONA"
    user_data[user_id] = {}
    
    await update.message.reply_text(
        "👋 Welcome! Let's set up your character wizard.\n\n"
        "Please send me the **Personality / System Prompt** for the character:"
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "WAITING_FOR_PERSONA"
    user_data[user_id] = {}
    if user_id in USER_MEMORIES:
        del USER_MEMORIES[user_id]
    if user_id in SYSTEM_PROMPTS:
        del SYSTEM_PROMPTS[user_id]
        
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
        
        SYSTEM_PROMPTS[user_id] = f"""
{persona}

Additional Guidelines:
{extra_rules}

CRITICAL LANGUAGE & FORMATTING RULES:
1. Language: You MUST speak in Hinglish (a natural conversational mix of Hindi and English words/phrases). Do NOT use pure English and do NOT use pure Hindi. Blend them smoothly just like modern everyday conversation.
2. Actions, movements, and scene descriptions MUST be enclosed in single backticks (e.g. `she glares angrily and crosses her arms`). This renders them in Telegram's distinct monospace font.
3. Spoken dialogue MUST be in normal text or double quotes (e.g. "Tum sudhroge nahi kya? Get up right now!").
"""

        USER_MEMORIES[user_id] = []
        
        try:
            await update.message.reply_text("🚀 Setup complete! Initializing roleplay...")
            
            intro_msg = f"Begin the roleplay based on this scenario: {scenario}"
            USER_MEMORIES[user_id].append({"role": "user", "parts": [{"text": intro_msg}]})
            
            response = gemini_client.models.generate_content(
                model=MODEL_ID,
                contents=USER_MEMORIES[user_id],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPTS[user_id],
                    temperature=0.85,
                    max_output_tokens=600,
                    safety_settings=SAFETY_CONFIG
                )
            )
            
            raw_text = response.text.strip() if response.text else ""
            USER_MEMORIES[user_id].append({"role": "model", "parts": [{"text": raw_text}]})
            await update.message.reply_text(raw_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error starting chat: {e}")
            await update.message.reply_text("`Character loaded, but failed to initialize scenario. Send a message to start roleplaying manually.`", parse_mode="Markdown")
            
    elif state == "ACTIVE":
        if user_id not in USER_MEMORIES:
            USER_MEMORIES[user_id] = []
            
        USER_MEMORIES[user_id].append({"role": "user", "parts": [{"text": text}]})
        
        try:
            response = gemini_client.models.generate_content(
                model=MODEL_ID,
                contents=USER_MEMORIES[user_id],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPTS.get(user_id, "You are a roleplay character."),
                    temperature=0.85,
                    max_output_tokens=600,
                    safety_settings=SAFETY_CONFIG
                )
            )
            
            raw_text = response.text.strip() if response.text else ""
            USER_MEMORIES[user_id].append({"role": "model", "parts": [{"text": raw_text}]})
            await update.message.reply_text(raw_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            await update.message.reply_text("`The character stares blankly, momentarily unresponsive.`", parse_mode="Markdown")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Hinglish Roleplay Bot is running with Gemini 3.1 Flash-Lite...")
    application.run_polling()

if __name__ == "__main__":
    main()

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
logger = logging.getLogger(__name__)

# Environment variables support
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Missing BOT_TOKEN/TELEGRAM_BOT_TOKEN or GEMINI_API_KEY in environment variables.")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-2.5-flash"

# User state storage
user_states = {}
user_data = {}
CHAT_SESSIONS = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "SETTING_PERSONA"
    user_data[user_id] = {
        "persona": "",
        "scenario": "",
        "rules": "",
        "photo_file_id": None,
        "user_name": ""
    }
    
    if user_id in CHAT_SESSIONS:
        del CHAT_SESSIONS[user_id]
    
    await update.message.reply_text(
        "👋 **Welcome to the Roleplay Bot Setup!**\n\n"
        "**Step 1 (SETTING_PERSONA):** Send your character's persona description.\n"
        "*(Aap jitne chahein utne messages mein lamba description bhej sakte hain.)*\n"
        "Jab complete ho jaye, tab **`/done`** type karein."
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "SETTING_PERSONA"
    user_data[user_id] = {
        "persona": "",
        "scenario": "",
        "rules": "",
        "photo_file_id": None,
        "user_name": ""
    }
    if user_id in CHAT_SESSIONS:
        del CHAT_SESSIONS[user_id]
        
    await update.message.reply_text(
        "🔄 **Session reset successfully!**\n\n"
        "**Step 1 (SETTING_PERSONA):** Send your character's persona description.\n"
        "Jab complete ho jaye, tab **`/done`** type karein."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_states:
        user_states[user_id] = "SETTING_PERSONA"
        user_data[user_id] = {"persona": "", "scenario": "", "rules": "", "photo_file_id": None, "user_name": ""}

    state = user_states[user_id]

    # Handle Step 4 Photo Upload directly if user sends a photo
    if state == "SETTING_PHOTO" and update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
        user_data[user_id]["photo_file_id"] = photo_file_id
        user_states[user_id] = "SETTING_USERNAME"
        
        await update.message.reply_photo(
            photo=photo_file_id,
            caption="🖼 📸 **Character Photo Received & Locked!**\n\n"
                    "**Step 5 (SETTING_USERNAME):** What is **your name** for the story? (e.g. Anurag)\n"
                    "Type your name and send it, then type **`/done`**."
        )
        return

    text = update.message.text.strip() if update.message.text else ""

    # Step 1: SETTING_PERSONA
    if state == "SETTING_PERSONA":
        if text.lower() == "/done":
            if not user_data[user_id]["persona"].strip():
                await update.message.reply_text("⚠️ Persona khali hai, pehle description bhejein.")
                return
            user_states[user_id] = "SETTING_SCENARIO"
            await update.message.reply_text(
                "✅ **Persona Saved!**\n\n"
                "**Step 2 (SETTING_SCENARIO):** Send the **Starting Scenario**.\n"
                "*(Multiple messages mein bhej sakte hain, khatam hone par `/done` likhein)*"
            )
            return
        else:
            if text:
                curr = user_data[user_id]["persona"]
                user_data[user_id]["persona"] = curr + "\n" + text if curr else text
                await update.message.reply_text("📥 Persona chunk added. Send more text or type **/done** to proceed.")
            return

    # Step 2: SETTING_SCENARIO
    elif state == "SETTING_SCENARIO":
        if text.lower() == "/done":
            if not user_data[user_id]["scenario"].strip():
                await update.message.reply_text("⚠️ Scenario khali hai, pehle description bhejein.")
                return
            user_states[user_id] = "SETTING_RULES"
            await update.message.reply_text(
                "✅ **Scenario Saved!**\n\n"
                "**Step 3 (SETTING_RULES):** Send additional rules or constraints (or type `none` to use default styling rules).\n"
                "*(Multiple messages mein bhej sakte hain, khatam hone par `/done` likhein)*"
            )
            return
        else:
            if text:
                curr = user_data[user_id]["scenario"]
                user_data[user_id]["scenario"] = curr + "\n" + text if curr else text
                await update.message.reply_text("📥 Scenario chunk added. Send more text or type **/done** to proceed.")
            return

    # Step 3: SETTING_RULES
    elif state == "SETTING_RULES":
        if text.lower() == "/done":
            if not user_data[user_id]["rules"].strip() or user_data[user_id]["rules"].lower() == "none":
                user_data[user_id]["rules"] = "Follow exact character persona, short crisp actions, and Hinglish style."
            user_states[user_id] = "SETTING_PHOTO"
            await update.message.reply_text(
                "✅ **Rules Saved!**\n\n"
                "**Step 4 (SETTING_PHOTO):** Send character photo now.\n"
                "👉 Agar photo skip karni hai, toh sirf **`none`** type karke bhej dein."
            )
            return
        else:
            if text:
                curr = user_data[user_id]["rules"]
                user_data[user_id]["rules"] = curr + "\n" + text if curr else text
                await update.message.reply_text("📥 Rules chunk added. Send more text or type **/done** to proceed.")
            return

    # Step 4: SETTING_PHOTO (Text choice 'none')
    elif state == "SETTING_PHOTO":
        if text.lower() == "none":
            user_data[user_id]["photo_file_id"] = None
            user_states[user_id] = "SETTING_USERNAME"
            await update.message.reply_text(
                "⏭️ **Photo skipped.**\n\n"
                "**Step 5 (SETTING_USERNAME):** What is **your name** for the story? (e.g. Anurag)\n"
                "Type your name and send it, then type **`/done`**."
            )
            return
        else:
            await update.message.reply_text("⚠️ Kripya character ki photo bhejein, ya skip karne ke liye **`none`** type karein.")
            return

    # Step 5: SETTING_USERNAME
    elif state == "SETTING_USERNAME":
        if text.lower() == "/done":
            if not user_data[user_id]["user_name"].strip():
                await update.message.reply_text("⚠️ Please enter your name before typing /done.")
                return
            
            user_states[user_id] = "ACTIVE"
            await initialize_active_session(update, user_id)
            return
        else:
            if text:
                curr = user_data[user_id]["user_name"]
                user_data[user_id]["user_name"] = curr + " " + text if curr else text
                await update.message.reply_text("📥 Name saved. Type **/done** to complete setup and start roleplay.")
            return

    # Step 6: ACTIVE Chat Mode using Official Gemini Chats API
    elif state == "ACTIVE":
        if user_id not in CHAT_SESSIONS:
            # Recreate chat session silently without restarting setup wizard
            await recreate_chat_session(user_id)
            
        try:
            chat = CHAT_SESSIONS[user_id]
            response = chat.send_message(text)
            
            raw_text = response.text.strip() if response.text else f"`She looks at {user_data[user_id]['user_name']} expectantly, waiting.`"
            await update.message.reply_text(raw_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            await update.message.reply_text(f"`She taps her desk sharply, looking straight at {user_data[user_id]['user_name']}. 'Say that again.'`", parse_mode="Markdown")

async def recreate_chat_session(user_id: int):
    data = user_data.get(user_id, {})
    persona = data.get("persona", "Strict professor")
    scenario = data.get("scenario", "In the office")
    rules = data.get("rules", "Hinglish short actions")
    user_name = data.get("user_name", "Anurag")

    system_prompt = f"""
[Character Persona]
{persona}

[Additional Guidelines & Rules]
{rules}

[User Information]
User's Name: {user_name}

CRITICAL STYLE & ANTI-LOOP RULES:
1. Language Style: Fluent Hinglish (natural mix of Hindi and English words/phrases).
2. Action Length: Keep actions short, crisp, and punchy (e.g., `she leans against the desk, smirking`). Avoid unnecessarily long paragraphs. Keep the conversation moving fast.
3. Formatting: Physical actions/movements MUST be enclosed in single backticks. Spoken dialogues in normal text or double quotes.
4. Always address and interact directly with the user as {user_name}.
5. NEVER repeat previous dialogue or actions. Always respond dynamically and creatively to the user's latest input.
"""

    safety_config = [
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    ]
    
    chat = gemini_client.chats.create(
        model=MODEL_ID,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.9,
            safety_settings=safety_config
        )
    )
    CHAT_SESSIONS[user_id] = chat

async def initialize_active_session(update: Update, user_id: int):
    data = user_data[user_id]
    scenario = data["scenario"]
    user_name = data["user_name"]
    photo_id = data["photo_file_id"]

    try:
        await update.message.reply_text("🚀 Setup complete! Launching roleplay...")
        
        if photo_id:
            await update.message.reply_photo(
                photo=photo_id,
                caption=f"✨ **Character Initialized**\nUser: {user_name}"
            )

        # Initialize the chat session
        await recreate_chat_session(user_id)
        chat = CHAT_SESSIONS[user_id]

        intro_msg = f"*(Scene starts: {scenario})* Begin the roleplay addressing {user_name} with your signature tone and short actions."
        response = chat.send_message(intro_msg)
        
        raw_text = response.text.strip() if response.text else f"`She glances up from her desk, her gaze locking onto {user_name}. 'Late again?'`"
        await update.message.reply_text(raw_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error starting chat: {e}")
        await update.message.reply_text(f"`She looks up, waiting for you to begin, {user_name}.`", parse_mode="Markdown")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO & (~filters.COMMAND), handle_message))

    print("Hinglish Short-Action Roleplay Bot is running successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()

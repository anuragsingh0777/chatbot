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

# 1. Suppress noisy httpx terminal logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. Initialize Google GenAI Client
client = genai.Client()

# 3. Bot State Storage (Advanced Multi-Step Setup Wizard)
user_sessions = {}


def get_or_create_session(user_id: int):
  if user_id not in user_sessions:
    user_sessions[user_id] = {
        "state": "IDLE",  # IDLE, SETTING_PERSONA, SETTING_SCENARIO, SETTING_RULES, SETTING_PHOTO, SETTING_USERNAME, ACTIVE
        "persona": "",
        "scenario": "",
        "rules": "",
        "char_photo_id": None,
        "user_name": "Anurag",  # Default fallback
        "temp_buffer": [],
        "chat_session": None,
    }
  return user_sessions[user_id]


# 4. Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  session = get_or_create_session(user_id)
  session["state"] = "SETTING_PERSONA"
  session["temp_buffer"] = []

  await update.message.reply_text(
      "🔥 **Roleplay Setup Wizard Started** 🔥\n\n"
      "Step 1: Please send your **Persona / System Prompt** parts in multiple"
      " messages if needed.\nWhen done sending all parts, type **/done**."
  )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  session = get_or_create_session(user_id)
  current_state = session["state"]

  if current_state == "SETTING_PERSONA":
    session["persona"] = "\n".join(session["temp_buffer"])
    session["temp_buffer"] = []
    session["state"] = "SETTING_SCENARIO"
    await update.message.reply_text(
        "✅ **Persona saved successfully!**\n\n"
        "Step 2: Now send your **Scenario** details. Type **/done** when finished."
    )

  elif current_state == "SETTING_SCENARIO":
    session["scenario"] = "\n".join(session["temp_buffer"])
    session["temp_buffer"] = []
    session["state"] = "SETTING_RULES"
    await update.message.reply_text(
        "✅ **Scenario saved successfully!**\n\n"
        "Step 3: Send any **Additional Rules / Constraints** (e.g. formatting"
        " rules, language style). Type **/done** when finished."
    )

  elif current_state == "SETTING_RULES":
    session["rules"] = "\n".join(session["temp_buffer"])
    session["temp_buffer"] = []
    session["state"] = "SETTING_PHOTO"
    await update.message.reply_text(
        "✅ **Rules saved successfully!**\n\n"
        "Step 4: Send a **Photo of the Character**.\n"
        "-> If you want to skip, simply type **none**.\n"
        "-> Otherwise, upload the image directly."
    )

  elif current_state == "SETTING_PHOTO":
    # If text command /done was sent during photo step without uploading an image, treat as 'none'
    session["char_photo_id"] = None
    session["state"] = "SETTING_USERNAME"
    await update.message.reply_text(
        "✅ **Photo step skipped.**\n\n"
        "Step 5: What is **your name** for the story? (e.g. Anurag)\n"
        "Type your name and send it."
    )

  elif current_state == "SETTING_USERNAME":
    # Captured from text handler if they used /done instead of just typing the name,
    # but normally step 5 expects direct text. We handle both.
    session["state"] = "ACTIVE"
    await initialize_active_session(update, session)

  else:
    await update.message.reply_text(
        "You are already in an active session! Use /reset to restart the"
        " configuration."
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  user_sessions[user_id] = {
      "state": "IDLE",
      "persona": "",
      "scenario": "",
      "rules": "",
      "char_photo_id": None,
      "user_name": "Anurag",
      "temp_buffer": [],
      "chat_session": None,
  }
  await update.message.reply_text(
      "🔄 Session reset completely. Type /start to begin the setup wizard again."
  )


async def initialize_active_session(update: Update, session: dict):
  # Construct system instruction incorporating all custom parameters
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

  # Create Gemini chat instance with safety bypass config
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

  await update.message.reply_text(
      "🎉 **Setup Complete! Roleplay is now ACTIVE.**\n"
      "Generating opening sequence..."
  )

  # Trigger opening response from the model automatically
  try:
    initial_prompt = (
        f"Begin the roleplay scenario immediately based on the starting"
        f" scenario. Address the user as {session['user_name']} and establish"
        f" the opening atmosphere."
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


# 6. Message Handler for Wizard Steps & Active Chat
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  session = get_or_create_session(user_id)
  state = session["state"]

  # Handle Photo Setup Step separately if image is uploaded
  if state == "SETTING_PHOTO":
    if update.message.photo:
      # Grab the highest resolution photo file ID
      photo_file_id = update.message.photo[-1].file_id
      session["char_photo_id"] = photo_file_id
      session["state"] = "SETTING_USERNAME"

      caption_text = (
          "📸 **Character Photo Received & Locked!**\n\n"
          "Step 5: What is **your name** for the story? (e.g. Anurag)\n"
          "Type your name and send it."
      )
      await update.message.reply_photo(photo=photo_file_id, caption=caption_text)
      return
    else:
      text = update.message.text.strip().lower()
      if text == "none":
        session["char_photo_id"] = None
        session["state"] = "SETTING_USERNAME"
        await update.message.reply_text(
            "✅ **Photo skipped.**\n\n"
            "Step 5: What is **your name** for the story? (e.g. Anurag)\n"
            "Type your name and send it."
        )
        return
      else:
        await update.message.reply_text(
            "Please upload a photo, or type **none** to skip this step."
        )
        return

  # Handle Username Setup Step
  if state == "SETTING_USERNAME":
    user_input_name = update.message.text.strip()
    session["user_name"] = (
        user_input_name if user_input_name else "Anurag"
    )
    session["state"] = "ACTIVE"
    await initialize_active_session(update, session)
    return

  # Handle Buffer Steps (Persona, Scenario, Rules)
  if state in ["SETTING_PERSONA", "SETTING_SCENARIO", "SETTING_RULES"]:
    text = update.message.text
    if text:
      session["temp_buffer"].append(text)
      await update.message.reply_text(
          "📥 Part received. Send more or type **/done** to proceed."
      )
    return

  # Handle Active Chat Generation with Blank/Error Safeguard Fix
  if state == "ACTIVE":
    chat = session.get("chat_session")
    if not chat:
      await update.message.reply_text(
          "⚠️ Session error detected. Please type /reset to start over."
      )
      return

    user_text = update.message.text
    if not user_text:
      return

    try:
      response = chat.send_message(user_text)

      # Blank Response / Safety Filter Fallback Fix
      if response and response.text:
        reply_text = response.text
      else:
        # Graceful fallback so bot never freezes or outputs blank messages
        reply_text = (
            "`She leans in closer, her breath warm against your skin, deeply"
            " absorbing your words without breaking eye contact...`"
        )

      # Telegram message length safety split (4096 character limit)
      if len(reply_text) > 4000:
        for i in range(0, len(reply_text), 4000):
          await update.message.reply_text(reply_text[i : i + 4000])
      else:
        await update.message.reply_text(reply_text)

    except Exception as e:
      logger.error(f"Error generating response: {e}")
      # Fallback message to prevent crashing or blank output errors
      await update.message.reply_text(
          "`She pauses for a fraction of a second, her gaze locking onto yours"
          " with an intense challenge, waiting for you to continue...`"
      )
  else:
    await update.message.reply_text(
        "Please type /start to begin the bot configuration wizard."
    )


def main():
  # Replace with your actual Telegram Bot Token or environment variable
  TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

  app = ApplicationBuilder().token(TOKEN).build()

  app.add_handler(CommandHandler("start", start_command))
  app.add_handler(CommandHandler("done", done_command))
  app.add_handler(CommandHandler("reset", reset_command))
  app.add_handler(
      MessageHandler(
          (filters.TEXT | filters.PHOTO) & (~filters.COMMAND), handle_message
      )
  )

  print("Bot is up and running with the new setup wizard...")
  app.run_polling()


if __name__ == "__main__":
  main()

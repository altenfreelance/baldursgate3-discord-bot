# discord_bot.py
import discord
from discord.ext import commands
import google.generativeai as genai
import os
import asyncio
import argparse
from dotenv import load_dotenv

# Import the core RAG processing logic
from gemini_bg3_rag import (
    process_query_with_rag_chat,
    DEFAULT_KNOWLEDGE_BASE_TOPIC  # Or import specific constants if needed
)

# --- Discord Bot Configuration ---
DISCORD_TOKEN_ENV = "DISCORD_BOT_TOKEN"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
DEFAULT_GEMINI_MODEL_ENV = "DEFAULT_GEMINI_MODEL"
DEFAULT_MODEL_NAME = "gemini-2.0-flash"

# --- Global Variables for the Bot ---
user_chat_sessions = {}  # {user_id: genai.ChatSession}
gemini_model_instance = None
bot_cli_verbose = False  # For CLI logging of bot actions, not RAG core

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


async def initialize_gemini_model():
    """Initializes the global Gemini model instance."""
    global gemini_model_instance
    api_key = os.environ.get(GEMINI_API_KEY_ENV)
    if not api_key:
        print("CRITICAL: GEMINI_API_KEY not found in environment.")
        return False

    model_name = os.environ.get(DEFAULT_GEMINI_MODEL_ENV, DEFAULT_MODEL_NAME)
    try:
        genai.configure(api_key=api_key)
        safety_settings_config = [
            {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for c in [
                "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"
            ]
        ]
        gemini_model_instance = genai.GenerativeModel(model_name, safety_settings=safety_settings_config)
        print(f"Gemini model '{model_name}' initialized successfully for the bot.")
        return True
    except Exception as e:
        print(f"CRITICAL: Error initializing Gemini model: {e}")
        return False


@bot.event
async def on_ready():
    global bot_cli_verbose
    # Command-line arguments for the bot script itself
    parser = argparse.ArgumentParser(description="Discord Bot with Gemini RAG Core")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose CLI logging for bot operations.")
    args, _ = parser.parse_known_args()
    bot_cli_verbose = args.verbose
    if bot_cli_verbose:
        print("Discord Bot: CLI verbose logging enabled.")

    if not await initialize_gemini_model():
        print("Bot cannot start due to Gemini model initialization failure. Check API key and configuration.")
        await bot.close()  # Stop the bot
        return

    print(f"🤖 {bot.user} (BG3 Bot Hopewell) is online!")
    print(f"Knowledge Base Topic: {DEFAULT_KNOWLEDGE_BASE_TOPIC}")  # Using the default from core
    print(
        f"Use !ask <query> to interact. Verbose RAG logging is controlled by gemini_rag_core's verbose flag (passed from here).")


@bot.command(name="ask")
async def ask(ctx: commands.Context, *, query: str):
    if not gemini_model_instance:
        await ctx.send("⚠️ The AI model isn't ready. Please tell the admin to check the bot console.")
        return

    user_id = ctx.author.id
    # Get or create chat session for the user
    if user_id not in user_chat_sessions:
        if bot_cli_verbose: print(f"Bot Verbose: Creating new chat session for user {user_id}")
        user_chat_sessions[user_id] = gemini_model_instance.start_chat(history=[])

    current_chat_session = user_chat_sessions[user_id]

    await ctx.send("🔍 Thinking...")
    try:
        # Run the synchronous RAG processing in a separate thread
        # Pass the bot's verbose flag to the RAG core's verbose flag
        response_text = await asyncio.to_thread(
            process_query_with_rag_chat,
            query,
            current_chat_session,  # Pass the specific user's session
            gemini_model_instance,
            DEFAULT_KNOWLEDGE_BASE_TOPIC,  # Can be made dynamic if needed
            bot_cli_verbose  # RAG core will use this for its own verbose prints
        )

        if len(response_text) > 1950:
            await ctx.send(f"🧠 **{bot.user.name} says:**\nThe answer is long, sending in parts:")
            for i in range(0, len(response_text), 1950):
                await ctx.send(response_text[i:i + 1950])
        else:
            await ctx.send(f"🧠 **{bot.user.name} says:**\n{response_text}")

    except Exception as e:
        print(f"Error in !ask command for user {user_id}: {e}")  # Log full error to console
        await ctx.send(f"⚠️ An unexpected error occurred. Please try again or contact an admin.")


@bot.command(name="newchat", aliases=["new", "reset"])
async def new_chat_command(ctx: commands.Context):  # Renamed to avoid conflict with any 'new' keyword
    user_id = ctx.author.id
    if user_id in user_chat_sessions:
        del user_chat_sessions[user_id]  # This removes the session, a new one will be made on next !ask
        await ctx.send(f"✨ Your conversation history with {bot.user.name} has been reset!")
        if bot_cli_verbose: print(f"Bot Verbose: Chat session reset for user {user_id}")
    else:
        await ctx.send("You don't have an active conversation to reset.")


# --- Main Entry Point for Bot ---
if __name__ == "__main__":
    load_dotenv()

    discord_token = os.environ.get(DISCORD_TOKEN_ENV)
    gemini_api_key = os.environ.get(GEMINI_API_KEY_ENV)  # Check early

    if not discord_token:
        print(f"CRITICAL: {DISCORD_TOKEN_ENV} not found in environment variables or .env file.")
    elif not gemini_api_key:  # Check if API key is present before attempting to run
        print(f"CRITICAL: {GEMINI_API_KEY_ENV} not found in environment. Bot will not start.")
    else:
        print("Starting Discord bot...")
        bot.run(discord_token)
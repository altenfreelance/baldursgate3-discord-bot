import discord
from discord.ext import commands
import asyncio
from qa import get_answer  # Assumes your QA logic is in qa.py

# Replace this with your actual bot token
DISCORD_TOKEN = "YOUR_DISCORD_BOT_TOKEN"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 HonorMind is online as {bot.user}!")

@bot.command(name="ask")
async def ask(ctx, *, query: str):
    await ctx.send("🔍 Thinking...")
    try:
        response = get_answer(query)
        await ctx.send(f"🧠 **HonorMind says:**\n{response}")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

bot.run(DISCORD_TOKEN)

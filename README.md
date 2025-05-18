# BG3 Bot

RAG Model Discord bot for Baldur's Gate 3

Uses Gemini and scraped bg3 wiki pages. Uses keyword generation to find good wiki pages to provide as context to gemini.

## Prereqs

- Python 3.12
- Recommended to use a venv

## Setup
### Install dependencies after activating venv

```
pip install -r requirements.txt
```

### Setup envars
Create a file called `.env` at the root of this project and fill these out. Gemini free tier works plenty well for this project. 
```dotenv
GEMINI_API_KEY=
DEFAULT_MODEL_NAME=gemini-2.0-flash
DISCORD_BOT_TOKEN=
```

### Gemini prereqs
https://aistudio.google.com/prompts/new_chat
There should be a get API key button at the top, the free tier is generous and sufficient for this app. 

### Get a Discord Bot Token, and invite it to a server
You will have to create an application https://discord.com/developers/applications/
Then find the bot tab and create a bot.
Then click Oath2 and create a share link. Give it the messaging permissions there are a few that make sense, but I didn't write them down. 

Navigate to that share link something like "https://discord.com/oauth2/authorize?client_id=xxxxxxxxxx&permissions=xxxxxx&integration_type=0&scope=bot" and you will be able to invite the bot to your discord server.

To bring the bot online simply run  
```
python discord_bot.py
```

## Development


### Updating Dependencies
If you install any new deps using pip to get something running, then also run

Run 
```
pip freeze > requirements.txt
```

### New Feature Ideas

Location Awareness - Looking to add location awareness so the bot can watch your coordinates and provide helpful info
Voice Interaction - Interact with the bot via voice

## Data
The data for this bot is in GitHub now here, no need to do anything else.

### How was the data generated?
Using `python sitemap_generator.py` 
Then extracting keywords using `python preprocess_keywords_from_wikis.py`


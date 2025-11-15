# 🥚 Egg Counter Bot (Testing Phase)

Egg Counter Bot is a Discord bot designed to count how many eggs you opened in a game by scanning webhook messages inside a specific channel.  
The project is **still in testing**, will evolve over time, and is **not affiliated with SpeedHubX**.

If you encounter any issue, feel free to contact me on Discord: **@darkhii1**.

Regular updates will be released.

---

# ⭐ Features
- Slash command: `/egg`
- Counts multiple egg types:
  - Paradise
  - Safari
  - All (combined)
- Flexible time filters:
  - today
  - 24h, 36h, 48h
  - one day
  - 2 days, 3 days
  - week
- Global correction multiplier for missing logs (`LOSS_MULT`)
- Timezone support
- Configurable with a `.env` file
- Works on any computer with Python 3

---

# 📘 How to Set Up and Use Egg Counter Bot

This guide explains how anyone can download, configure, and run the bot on their own Discord server.

---

# 🟦 1. Requirements
- Discord account  
- Discord server with permission to add bots  
- Python 3.10+  
- (Optional) Git  

---

# 🟩 2. Download the project

## Option A — Clone with Git
```bash
git clone https://github.com/darkhii1/egg-counter-bot.git
cd egg-counter-bot
```

## Option B — Download ZIP
1. Download ZIP from GitHub  
2. Extract it  
3. Open a terminal in the extracted folder  

---

# 🟧 3. Install dependencies
```bash
pip install -r requirements.txt
```

---

# 🟥 4. Create your own Discord bot

1. Go to https://discord.com/developers/applications  
2. Create a new application  
3. Go to **Bot → Add Bot**  
4. Copy the **TOKEN**  
5. Enable **MESSAGE CONTENT INTENT**  
6. Go to **OAuth2 → URL Generator**  
   - Scopes: `bot`, `applications.commands`  
   - Permissions:  
     - Read Messages  
     - Read Message History  
     - Send Messages  
7. Invite the bot to your server  

---

# 🟨 5. Configure the `.env` file

Duplicate the example file:

```bash
cp .env.example .env
```

Edit `.env`:

```
DISCORD_TOKEN=YOUR_BOT_TOKEN
GUILD_ID=YOUR_SERVER_ID
CHANNEL_ID=YOUR_CHANNEL_ID
ONLY_WEBHOOK=1
TZ_OFFSET_HOURS=1
EGG_PARADISE_PATTERN=(?i)paradise
EGG_SAFARI_PATTERN=(?i)safari
LOSS_MULT=1.0
```

---

# 🟦 6. Run the bot
```bash
python main.py
```

---

# 🟩 7. Using `/egg`

Examples:

```
/egg
/egg egg_type:safari
/egg when:24h
/egg egg_type:paradise when:36h
```

---

# 🟪 8. Troubleshooting
- Check `.env` values  
- Verify bot permissions  
- Ensure correct server and channel IDs  

For help, contact **@darkhii1** on Discord.

---

# 🟫 9. Disclaimer
This project is **not affiliated with SpeedHubX**.  
It is in **testing phase**. Updates will be released regularly.

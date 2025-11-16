# Egg Counter Bot  
### Realtime Discord Egg Tracking System

A minimal, efficient, and extensible Discord bot designed to track egg hatch events in real time.  
Built with performance, accuracy, and simplicity in mind.

---

## Overview

Egg Counter Bot monitors a specific Discord channel, identifies egg-related messages, and tracks hatch counts both in real-time and across message history.  
Using a lightweight SQLite database, it stores daily totals, supports history lookups, and delivers a daily summary report automatically.

This project prioritizes:  
- Fast message processing  
- Clean code structure  
- Low resource usage  
- Accurate and consistent egg tracking  

---

## Features

### Realtime Tracking  
The bot updates egg counts the moment new messages are received.  
Counts persist across restarts.

### History Scanning  
Commands allow scanning message history for:  
- Today  
- Last 24 hours  
- Last N hours  
- Last N days  
- Last week  
- All-time (from persistent database)

### Automatic Egg Type Detection  
If users mention new egg types, the bot identifies them dynamically and stores them permanently.

### Daily Report  
At local midnight, the bot:  
1. Sends a private summary report to the configured user  
2. Stores metrics for the day  
3. Cleans data older than 14 days  
4. Resets today’s counters (optional)

### SQLite Persistence  
All egg types and daily totals are retained.  
No external database is required.

### Administration Tools  
Admins may:  
- Add new egg types  
- Remove existing ones  
- Assign custom emojis  
- Reset counters  
Directly through slash commands.

### Clean Embedded Output  
Reports and command outputs are formatted using consistent, minimal embeds.

---

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR-USERNAME/egg-counter-bot.git
cd egg-counter-bot
```

# 2. Install Dependencies
```bash
pip install -r requirements.txt
```
# 3. Configure Environment Variables

Create a .env file in the project directory:

```bash
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
CHANNEL_ID=YOUR_CHANNEL_ID
GUILD_ID=YOUR_GUILD_ID
REPORT_USER_ID=YOUR_USER_ID
TZ_OFFSET_HOURS=5.5

ONLY_WEBHOOK=0
```
# 4. Start the Bot
```bash
python main.py
```
# Commands 

/egg

Count egg hatches for any timeframe.

Examples:

/egg

/egg egg_type:paradise

/egg when:24h

/egg when:7d

/egg_trend

Compare today’s total vs yesterday.

Admin Commands

/egg_addtype name pattern emoji?

/egg_removetype name

/egg_setemoji name emoji

/egg_reset [name]


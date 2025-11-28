# main.py — Final corrected file (LIVE tracking + history scans + SQLite persistence)
# Paste this over your existing main.py

import os
import re
import sqlite3
import asyncio
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIG ----------------
TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
GUILD_ID = int(os.environ["GUILD_ID"])
REPORT_USER_ID = int(os.environ.get("REPORT_USER_ID", "781091697106223104"))

ONLY_WEBHOOK = os.environ.get("ONLY_WEBHOOK", "0") == "1"
TZ_OFFSET = float(os.environ.get("TZ_OFFSET_HOURS", "5.5"))  # e.g. 5.5
RESET_AFTER_REPORT = True
KEEP_DAYS = 14

DB_PATH = "eggs.db"

# ---------------- PATTERNS / LABELS / EMOJIS ----------------
PATTERN_MAP: Dict[str, re.Pattern] = {
    "paradise": re.compile(os.environ.get("EGG_PARADISE_PATTERN", r"(?i)\bparadise\b")),
    "safari":   re.compile(os.environ.get("EGG_SAFARI_PATTERN",   r"(?i)\bsafari\b")),
    "spooky":   re.compile(os.environ.get("EGG_SPOOKY_PATTERN",   r"(?i)\bspooky\b")),
    "summer":   re.compile(os.environ.get("EGG_SUMMER_PATTERN",   r"(?i)\bsummer\b")),
    "bee":      re.compile(os.environ.get("EGG_BEE_PATTERN",      r"(?i)\bbee\b")),
    "anti_bee": re.compile(os.environ.get("EGG_ANTI_BEE_PATTERN", r"(?i)\banti ?bee\b")),
    "night":    re.compile(os.environ.get("EGG_NIGHT_PATTERN",    r"(?i)\bnight\b")),
    "bug":      re.compile(os.environ.get("EGG_BUG_PATTERN",      r"(?i)\bbug\b")),
    "jungle":   re.compile(os.environ.get("EGG_JUNGLE_PATTERN",   r"(?i)\bjungle\b")),
    "gem":      re.compile(os.environ.get("EGG_GEM_PATTERN",      r"(?i)\bgem\b")),
}

def label_for_type(t: str) -> str:
    return {
        "paradise": "Paradise Egg",
        "safari": "Safari Egg",
        "spooky": "Spooky Egg",
        "summer": "Summer Egg",
        "bee": "Bee Egg",
        "anti_bee": "Anti Bee Egg",
        "night": "Night Egg",
        "bug": "Bug Egg",
        "jungle": "Jungle Egg",
        "gem": "Gem Egg",
    }.get(t, t)

EGG_EMOJIS: Dict[str, str] = {
    "paradise": "🪺","safari":"🐾","spooky":"👻","summer":"🌴",
    "bee":"🐝","anti_bee":"🚫🐝","night":"🌙","bug":"🐛","jungle":"🦜","gem":"💎"
}

AUTO_EMOJI_POOL = ["💠","🔮","✨","💎","🧿","🪄","🪙","🔹","🔸","🌟","🥚"]
EMBED_COLOR = 0x00FF88
# ---------------- DISCORD SETUP ----------------
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# in-memory live counters (persisted to DB periodically / on update)
egg_counts: Dict[str, int] = {name: 0 for name in PATTERN_MAP.keys()}
counts_lock = asyncio.Lock()

# DB connection + locks
_db_conn: Optional[sqlite3.Connection] = None
_db_lock = asyncio.Lock()
# ---------------- DB HELPERS ----------------
def _create_tables(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS egg_types (
        name TEXT PRIMARY KEY,
        pattern TEXT NOT NULL,
        emoji TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS egg_counts_today (
        egg_type TEXT PRIMARY KEY,
        count INTEGER NOT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS egg_counts_daily (
        date TEXT NOT NULL,
        egg_type TEXT NOT NULL,
        count INTEGER NOT NULL,
        PRIMARY KEY(date, egg_type)
    )""")
    conn.commit()

async def db_init():
    global _db_conn
    loop = asyncio.get_running_loop()
    def _open():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        _create_tables(conn)
        return conn
    _db_conn = await loop.run_in_executor(None, _open)

async def db_close():
    global _db_conn
    if _db_conn:
        await asyncio.get_running_loop().run_in_executor(None, _db_conn.close)
        _db_conn = None

async def db_execute(query: str, params: Tuple = ()):
    async with _db_lock:
        loop = asyncio.get_running_loop()
        def _exec():
            cur = _db_conn.cursor()
            cur.execute(query, params)
            _db_conn.commit()
            return cur
        return await loop.run_in_executor(None, _exec)

async def db_fetchall(query: str, params: Tuple = ()):
    async with _db_lock:
        loop = asyncio.get_running_loop()
        def _fetch():
            cur = _db_conn.cursor()
            cur.execute(query, params)
            return cur.fetchall()
        return await loop.run_in_executor(None, _fetch)

# persistence helpers
async def persist_today_count(egg_type: str, count: int):
    await db_execute("INSERT OR REPLACE INTO egg_counts_today(egg_type, count) VALUES(?, ?)", (egg_type, count))

async def persist_type(name: str, pattern: str, emoji: Optional[str] = None):
    await db_execute("INSERT OR REPLACE INTO egg_types(name, pattern, emoji) VALUES(?, ?, ?)", (name, pattern, emoji))

async def load_persisted_types():
    rows = await db_fetchall("SELECT name, pattern, emoji FROM egg_types")
    for name, pattern, emoji in rows:
        try:
            PATTERN_MAP[name] = re.compile(pattern)
            if emoji:
                EGG_EMOJIS[name] = emoji
            egg_counts.setdefault(name, 0)
        except re.error:
            print("Invalid regex in DB for", name)

async def load_today_counts():
    rows = await db_fetchall("SELECT egg_type, count FROM egg_counts_today")
    async with counts_lock:
        for et, cnt in rows:
            egg_counts[et] = cnt

async def persist_daily_totals(date_str: str, totals: Dict[str,int]):
    for name, cnt in totals.items():
        await db_execute("INSERT OR REPLACE INTO egg_counts_daily(date, egg_type, count) VALUES(?, ?, ?)", (date_str, name, cnt))

async def cleanup_old_daily_rows(keep_days: int):
    cutoff = (datetime.utcnow().date() - timedelta(days=keep_days)).isoformat()
    await db_execute("DELETE FROM egg_counts_daily WHERE date < ?", (cutoff,))
    # vacuum
    async with _db_lock:
        await asyncio.get_running_loop().run_in_executor(None, _db_conn.execute, "VACUUM")
        await asyncio.get_running_loop().run_in_executor(None, _db_conn.commit)

# ---------------- TEXT EXTRACTION ----------------
def extract_text(msg: discord.Message) -> str:
    parts = []
    if msg.content:
        parts.append(msg.content)
    for e in msg.embeds:
        if e.title: parts.append(e.title)
        if e.description: parts.append(e.description)
        for f in e.fields:
            if f.name: parts.append(f.name)
            if f.value: parts.append(f.value)
        if getattr(e, "image", None) and getattr(e.image, "url", None):
            parts.append(e.image.url.split("/")[-1])
        if getattr(e, "thumbnail", None) and getattr(e.thumbnail, "url", None):
            parts.append(e.thumbnail.url.split("/")[-1])
    for a in msg.attachments:
        parts.append(a.filename)
    return " ".join(parts)

# ---------------- HISTORY SCANS ----------------
async def fast_count_single(channel: discord.TextChannel, since, before, rx: re.Pattern):
    total = 0
    async for msg in channel.history(limit=None, after=since, before=before):
        if ONLY_WEBHOOK and not msg.webhook_id:
            continue
        total += len(rx.findall(extract_text(msg)))
    return total

async def fast_count_all(channel: discord.TextChannel, since, before):
    totals = {name: 0 for name in PATTERN_MAP.keys()}
    async for msg in channel.history(limit=None, after=since, before=before):
        if ONLY_WEBHOOK and not msg.webhook_id:
            continue
        text = extract_text(msg)
        for name, rx in PATTERN_MAP.items():
            totals[name] += len(rx.findall(text))
    return totals

# ---------------- UTIL ----------------
def assign_auto_emoji(name: str) -> str:
    if name in EGG_EMOJIS:
        return EGG_EMOJIS[name]
    idx = sum(ord(c) for c in name) % len(AUTO_EMOJI_POOL)
    emoji = AUTO_EMOJI_POOL[idx]
    EGG_EMOJIS[name] = emoji
    return emoji

def local_midnight(now_utc: datetime) -> datetime:
    local = now_utc + timedelta(hours=TZ_OFFSET)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local - timedelta(hours=TZ_OFFSET)
# ---------------- LIVE TRACKING (on_message) ----------------
@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.id != CHANNEL_ID:
        return

    text = extract_text(message)
    if not text:
        return

    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9_]+", lowered)

    # 1) Auto-detect new egg types (persist them)
    for t in tokens:
        if t.endswith("egg"):
            base = t[:-3].strip("_")
            if base and base not in PATTERN_MAP:
                pat = rf"(?i)\b{re.escape(base)}\b"
                PATTERN_MAP[base] = re.compile(pat)
                egg_counts[base] = 0
                assign_auto_emoji(base)
                await persist_type(base, pat, EGG_EMOJIS.get(base))
        elif t.startswith("egg"):
            base = t[3:].strip("_")
            if base and base not in PATTERN_MAP:
                pat = rf"(?i)\b{re.escape(base)}\b"
                PATTERN_MAP[base] = re.compile(pat)
                egg_counts[base] = 0
                assign_auto_emoji(base)
                await persist_type(base, pat, EGG_EMOJIS.get(base))

    # 2) Live counting (always)
    async with counts_lock:
        for name, rx in PATTERN_MAP.items():
            hits = rx.findall(text)
            if hits:
                egg_counts[name] = egg_counts.get(name, 0) + len(hits)
                # persist today's count (keeps counts across restarts)
                await persist_today_count(name, egg_counts[name])

# ---------------- DAILY REPORT + CLEANUP TASK ----------------
async def daily_report_task():
    await client.wait_until_ready()
    try:
        user = await client.fetch_user(REPORT_USER_ID)
    except Exception:
        print("Daily report user not found")
        user = None

    while True:
        now = datetime.now(timezone.utc)
        next_mid = (local_midnight(now) + timedelta(days=1))  # next local midnight in UTC
        wait = (next_mid - now).total_seconds()
        if wait <= 0:
            wait = 1
        await asyncio.sleep(wait)

        # snapshot & embed
        async with counts_lock:
            snapshot = dict(egg_counts)
        embed = discord.Embed(title="📊 Daily Egg Report", color=EMBED_COLOR, timestamp=datetime.now(timezone.utc))
        total = 0
        for name in sorted(snapshot.keys()):
            v = snapshot[name]; total += v
            embed.add_field(name=f"{EGG_EMOJIS.get(name,'🥚')} {label_for_type(name)}", value=str(v), inline=True)
        embed.add_field(name="TOTAL", value=str(total), inline=False)

        if user:
            try:
                await user.send(embed=embed)
            except Exception as e:
                print("Daily DM failed:", e)

        # persist daily totals for the day we just finished
        date_for = (next_mid - timedelta(days=1)).date().isoformat()
        await persist_daily_totals(date_for, snapshot)

        # cleanup old rows
        await cleanup_old_daily_rows(KEEP_DAYS)

        # reset today's counts (if configured)
        if RESET_AFTER_REPORT:
            async with counts_lock:
                for k in list(egg_counts.keys()):
                    egg_counts[k] = 0
            await db_execute("DELETE FROM egg_counts_today")
            # re-persist types metadata to ensure nothing lost
            for name, rx in PATTERN_MAP.items():
                await persist_type(name, rx.pattern, EGG_EMOJIS.get(name))

# ---------------- COMMANDS ----------------
@tree.command(
    name="egg",
    description="Count hatched eggs (today, 24h, 7d, custom)"
)
@app_commands.describe(egg_type="Type of egg", when="today, 24h, 7d, 14d, N hours/days")
@app_commands.choices(egg_type=[app_commands.Choice(name=n, value=n) for n in list(PATTERN_MAP.keys()) + ["all"]])
async def egg_cmd(
    interaction: discord.Interaction,
    egg_type: Optional[app_commands.Choice[str]] = None,
    when: Optional[str] = None
):
    await interaction.response.defer(thinking=True)
    et = egg_type.value if egg_type else "all"
    now = datetime.now(timezone.utc)
    s = (when or "").strip().lower()

    # TODAY -> live fast
    if s == "" or "today" in s:
        async with counts_lock:
            if et == "all":
                embed = discord.Embed(title="🥚 Today's Egg Breakdown", color=EMBED_COLOR)
                total = 0
                for name, value in egg_counts.items():
                    embed.add_field(name=f"{EGG_EMOJIS.get(name,'🥚')} {label_for_type(name)}", value=str(value), inline=True)
                    total += value
                embed.add_field(name="TOTAL", value=str(total), inline=False)
                await interaction.followup.send(embed=embed)
                return
            else:
                value = egg_counts.get(et, 0)
                embed = discord.Embed(title=f"{EGG_EMOJIS.get(et,'🥚')} {label_for_type(et)} (today)", color=EMBED_COLOR)
                embed.add_field(name="Count", value=str(value))
                await interaction.followup.send(embed=embed)
                return

    # parse history ranges
    def parse_when(s_in: str):
        if "all" == s_in:
            return None, "all time"
        if "24" in s_in:
            return now - timedelta(hours=24), "last 24h"
        if "7" in s_in or "week" in s_in:
            return now - timedelta(days=7), "last 7 days"
        if "14" in s_in:
            return now - timedelta(days=14), "last 14 days"
        m_h = re.search(r"(\d+)\s*h", s_in)
        if m_h:
            h = int(m_h.group(1)); return now - timedelta(hours=h), f"last {h}h"
        m_d = re.search(r"(\d+)\s*d", s_in)
        if m_d:
            d = int(m_d.group(1)); return now - timedelta(days=d), f"last {d} days"
        # fallback: today
        return local_midnight(now), "today"

    since, label = parse_when(s)

    ch = client.get_channel(CHANNEL_ID)
    if ch is None:
        await interaction.followup.send("Channel not found.")
        return

    if label == "all time":
        rows = await db_fetchall("SELECT egg_type, SUM(count) FROM egg_counts_daily GROUP BY egg_type")
        totals = {name: 0 for name in PATTERN_MAP.keys()}
        for r in rows:
            totals[r[0]] = r[1] or 0
        total = sum(totals.values())
        embed = discord.Embed(title="🥚 All-time Egg Totals", color=EMBED_COLOR)
        for name, val in totals.items():
            embed.add_field(name=f"{EGG_EMOJIS.get(name,'🥚')} {label_for_type(name)}", value=str(val), inline=True)
        embed.add_field(name="TOTAL", value=str(total), inline=False)
        await interaction.followup.send(embed=embed)
        return

    # run history scans (full scan between since -> now)
    if et == "all":
        totals = await fast_count_all(ch, since, None)
        total = sum(totals.values())
        embed = discord.Embed(title=f"🥚 Egg Count ({label})", color=EMBED_COLOR)
        for name, val in totals.items():
            embed.add_field(name=f"{EGG_EMOJIS.get(name,'🥚')} {label_for_type(name)}", value=str(val), inline=True)
        embed.add_field(name="TOTAL", value=str(total), inline=False)
        await interaction.followup.send(embed=embed)
    else:
        cnt = await fast_count_single(ch, since, None, PATTERN_MAP[et])
        embed = discord.Embed(title=f"{EGG_EMOJIS.get(et,'🥚')} {label_for_type(et)} ({label})", color=EMBED_COLOR)
        embed.add_field(name="Count", value=str(cnt))
        await interaction.followup.send(embed=embed)

# ---------------- /egg_trend ----------------
@tree.command(name="egg_trend", description="Compare today's total vs yesterday.")
async def egg_trend(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    now = datetime.now(timezone.utc)
    today_start = local_midnight(now)
    yesterday_start = today_start - timedelta(days=1)
    today_total = sum(egg_counts.values())

    ch = client.get_channel(CHANNEL_ID)
    if ch is None:
        await interaction.followup.send("Channel not found.")
        return

    yesterday_totals = await fast_count_all(ch, yesterday_start, today_start)
    yesterday_total = sum(yesterday_totals.values())
    diff = today_total - yesterday_total
    emoji = "📈" if diff >= 0 else "📉"
    embed = discord.Embed(title="📊 Egg Trend", color=0xFFD700,
                          description=f"**Today:** {today_total}\n**Yesterday:** {yesterday_total}\n\n**Trend:** {emoji} {abs(diff)} eggs")
    await interaction.followup.send(embed=embed)

# ---------------- ADMIN (add/remove/setemoji/reset) ----------------
def is_admin_interaction(interaction: discord.Interaction) -> bool:
    try:
        perms = interaction.user.guild_permissions
        return perms.administrator or perms.manage_guild
    except Exception:
        return False

@tree.command(name="egg_addtype", description="(Admin) Add new egg type")
@app_commands.describe(name="internal name (no spaces)", pattern="regex pattern (eg (?i)crystal)", emoji="optional emoji")
async def egg_addtype(interaction: discord.Interaction, name: str, pattern: str, emoji: Optional[str] = None):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("Admin only.", ephemeral=True)
        return
    if name in PATTERN_MAP:
        await interaction.response.send_message(f"{name} already exists.", ephemeral=True)
        return
    try:
        rx = re.compile(pattern)
    except re.error as e:
        await interaction.response.send_message(f"Invalid regex: {e}", ephemeral=True)
        return
    PATTERN_MAP[name] = rx
    egg_counts[name] = 0
    if emoji:
        EGG_EMOJIS[name] = emoji
    else:
        assign_auto_emoji(name)
    await persist_type(name, pattern, EGG_EMOJIS.get(name))
    await persist_today_count(name, 0)
    await interaction.response.send_message(f"Added `{name}`.", ephemeral=True)

@tree.command(name="egg_removetype", description="(Admin) Remove egg type")
@app_commands.describe(name="internal name")
async def egg_removetype(interaction: discord.Interaction, name: str):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("Admin only.", ephemeral=True)
        return
    if name not in PATTERN_MAP:
        await interaction.response.send_message(f"{name} not found.", ephemeral=True)
        return
    PATTERN_MAP.pop(name, None)
    egg_counts.pop(name, None)
    EGG_EMOJIS.pop(name, None)
    await db_execute("DELETE FROM egg_types WHERE name = ?", (name,))
    await db_execute("DELETE FROM egg_counts_today WHERE egg_type = ?", (name,))
    await db_execute("DELETE FROM egg_counts_daily WHERE egg_type = ?", (name,))
    await interaction.response.send_message(f"Removed `{name}`.", ephemeral=True)

@tree.command(name="egg_setemoji", description="(Admin) Set emoji")
@app_commands.describe(name="internal name", emoji="emoji to set")
async def egg_setemoji(interaction: discord.Interaction, name: str, emoji: str):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("Admin only.", ephemeral=True)
        return
    if name not in PATTERN_MAP:
        await interaction.response.send_message(f"{name} not found.", ephemeral=True)
        return
    EGG_EMOJIS[name] = emoji
    await persist_type(name, PATTERN_MAP[name].pattern, emoji)
    await interaction.response.send_message(f"Set emoji for `{name}` to {emoji}", ephemeral=True)

@tree.command(name="egg_reset", description="(Admin) Reset counts")
@app_commands.describe(name="type to reset (omit to reset all)")
async def egg_reset(interaction: discord.Interaction, name: Optional[str] = None):
    if not is_admin_interaction(interaction):
        await interaction.response.send_message("Admin only.", ephemeral=True)
        return
    async with counts_lock:
        if name:
            if name not in egg_counts:
                await interaction.response.send_message(f"{name} not found.", ephemeral=True)
                return
            egg_counts[name] = 0
            await persist_today_count(name, 0)
            await interaction.response.send_message(f"Reset {name}.", ephemeral=True)
        else:
            for k in list(egg_counts.keys()):
                egg_counts[k] = 0
                await persist_today_count(k, 0)
            await interaction.response.send_message("Reset all counts.", ephemeral=True)

# ---------------- ON_READY ----------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user} - initializing DB and loading state...")
    await db_init()
    await load_persisted_types()
    await load_today_counts()
    # ensure egg_counts contains persisted types
    async with counts_lock:
        for k in PATTERN_MAP.keys():
            egg_counts.setdefault(k, 0)

    # start background tasks
    # preload disabled intentionally (avoids startup lag)
    client.loop.create_task(daily_report_task())

    guild = discord.Object(id=GUILD_ID)
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="ur eggs"))
    print("Initialization complete. LIVE tracking active. History enabled.")

# ---------------- RUN ----------------
async def main():
    try:
        async with client:
            await client.start(TOKEN)
    finally:
        await db_close()

if __name__ == "__main__":
    asyncio.run(main())

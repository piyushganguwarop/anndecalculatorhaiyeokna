import os, re, asyncio
from typing import Optional
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from dotenv import load_dotenv
load_dotenv()

# ----- Secrets / Config -----
TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
GUILD_ID = int(os.environ["GUILD_ID"])

ONLY_WEBHOOK = os.environ.get("ONLY_WEBHOOK", "0") == "1"
TZ_OFFSET = int(os.environ.get("TZ_OFFSET_HOURS", "0"))

# ----- Load regex patterns -----
PAT_PARADISE = os.environ.get("EGG_PARADISE_PATTERN", "(?i)paradise")
PAT_SAFARI   = os.environ.get("EGG_SAFARI_PATTERN", "(?i)safari")
PAT_SPOOKY   = os.environ.get("EGG_SPOOKY_PATTERN", "(?i)spooky")
PAT_RARE     = os.environ.get("EGG_RARE_PATTERN", "(?i)rare")
PAT_RSUMMER   = os.environ.get("EGG_SUMMER_PATTERN", "(?i)rsummer")
PAT_BEE      = os.environ.get("EGG_BEE_PATTERN", "(?i)bee")
PAT_ANTI_BEE = os.environ.get("EGG_ANTI_BEE_PATTERN", "(?i)anti ?bee")
PAT_NIGHT    = os.environ.get("EGG_NIGHT_PATTERN", "(?i)night")
PAT_BUG      = os.environ.get("EGG_BUG_PATTERN", "(?i)bug")
PAT_JUNGLE   = os.environ.get("EGG_JUNGLE_PATTERN", "(?i)jungle")
PAT_GEM = os.environ.get("EGG_GEM_PATTERN", "(?i)gem")


# ----- Compile all patterns -----
RX_PARADISE = re.compile(PAT_PARADISE)
RX_SAFARI = re.compile(PAT_SAFARI)
RX_SPOOKY = re.compile(PAT_SPOOKY)
RX_RARE = re.compile(PAT_RARE)
RX_RSUMMER = re.compile(PAT_RSUMMER)
RX_BEE = re.compile(PAT_BEE)
RX_ANTI_BEE = re.compile(PAT_ANTI_BEE)
RX_NIGHT = re.compile(PAT_NIGHT)
RX_BUG = re.compile(PAT_BUG)
RX_JUNGLE = re.compile(PAT_JUNGLE)
RX_GEM = re.compile(PAT_GEM)


# ----- Mapping for easy extension -----
PATTERN_MAP = {
    "paradise": RX_PARADISE,
    "safari": RX_SAFARI,
    "spooky": RX_SPOOKY,
    "rare": RX_RARE,
    "raresummer": RX_RSUMMER,
    "bee": RX_BEE,
    "anti_bee": RX_ANTI_BEE,
    "night": RX_NIGHT,
    "bug": RX_BUG,
    "jungle": RX_JUNGLE,
    "gem": RX_GEM,
}

def label_for_type(egg_type: str) -> str:
    return {
        "paradise": "Paradise Egg",
        "safari": "Safari Egg",
        "spooky": "Spooky Egg",
        "rare": "Rare Egg",
        "raresummer": "Rare Summer Egg",
        "bee": "Bee Egg",
        "anti_bee": "Anti Bee Egg",
        "night": "Night Egg",
        "bug": "Bug Egg",
        "jungle": "Jungle Egg",
        "gem": "Gem Egg",
        "all": "All Eggs",
    }[egg_type]

# ----- Discord setup -----
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ----- Utils -----
def extract_text(msg: discord.Message) -> str:
    parts = []

    if msg.content:
        parts.append(msg.content)

    for e in msg.embeds:
        if e.title:
            parts.append(e.title)
        if e.description:
            parts.append(e.description)
        for f in e.fields:
            if f.name:
                parts.append(f.name)
            if f.value:
                parts.append(f.value)

    return " ".join(parts)

async def fast_count_single(channel, since, before, rx):
    total = 0

    async for msg in channel.history(
        limit=None,
        after=since,
        before=before,
        oldest_first=False
    ):
        if ONLY_WEBHOOK and not msg.webhook_id:
            continue

        body = extract_text(msg)
        total += len(rx.findall(body))

    return total
async def fast_count_all(channel, since, before):
    totals = {name: 0 for name in PATTERN_MAP}

    async for msg in channel.history(
        limit=None,
        after=since,
        before=before,
        oldest_first=False
    ):
        if ONLY_WEBHOOK and not msg.webhook_id:
            continue

        body = extract_text(msg)

        for name, rx in PATTERN_MAP.items():
            totals[name] += len(rx.findall(body))

    return totals

async def count_occurrences_all(channel, egg_type, since, before):
    # Count everything in ONE scan
    if egg_type == "all":
        totals = await fast_count_all(channel, since, before)
        return sum(totals.values())

    # Count a single egg type
    return await fast_count_single(
        channel,
        since,
        before,
        PATTERN_MAP[egg_type]
    )

    # ---- Optimized ALL-eggs mode ----
    # Reads messages only ONCE
    totals = {name: 0 for name in PATTERN_MAP.keys()}

    async for m in channel.history(after=since, before=before, oldest_first=False, limit=None):
        if ONLY_WEBHOOK and not m.webhook_id:
            continue

        body = m.content or ""
        if m.embeds:
            for e in m.embeds:
                if e.title:
                    body += " " + e.title
                if e.description:
                    body += " " + e.description
                for f in e.fields:
                    if f.name:
                        body += " " + f.name
                    if f.value:
                        body += " " + f.value

        # Run all regexes ONCE per message
        for name, rx in PATTERN_MAP.items():
            hits = rx.findall(body)
            if hits:
                totals[name] += len(hits)

    # Return total across all egg types
    return sum(totals.values())


def local_midnight_utc(now):
    local = now + timedelta(hours=TZ_OFFSET)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(hours=TZ_OFFSET)

def parse_when(when, now):
    if not when or not when.strip():
        since = local_midnight_utc(now)
        return since, None, "today"

    s = when.strip().lower()

    if "today" in s:
        since = local_midnight_utc(now)
        return since, None, "today"

    if "week" in s:
        since = now - timedelta(days=7)
        return since, None, "last 7 days"

    if "last 24" in s:
        since = now - timedelta(hours=24)
        return since, None, "last 24h"

    m_h = re.search(r"(\d+)\s*h", s)
    if m_h:
        h = int(m_h.group(1))
        since = now - timedelta(hours=h)
        return since, None, f"last {h}h"

    m_d = re.search(r"(\d+)\s*day") or re.search(r"(\d+)\s*d\b")
    if m_d:
        d = int(m_d.group(1))
        since = now - timedelta(days=d)
        return since, None, f"last {d} days"

    since = local_midnight_utc(now)
    return since, None, "today"

# ----- Slash Command -----
@tree.command(
    name="egg",
    description="Count hatched eggs (today, 24h, one day, 2 days, week, etc)"
)
@app_commands.choices(
    egg_type=[
        app_commands.Choice(name=et, value=et)
        for et in list(PATTERN_MAP.keys()) + ["all"]
    ]
)
@app_commands.describe(
    egg_type="Choose egg type",
    when="Period: today, 24h, 2 days, week..."
)
async def egg(
    interaction: discord.Interaction,
    egg_type: Optional[app_commands.Choice[str]] = None,
    when: Optional[str] = None
):
    await interaction.response.defer(thinking=True)

    et = egg_type.value if egg_type else "all"
    ch = interaction.client.get_channel(CHANNEL_ID)

    if ch is None:
        await interaction.followup.send("Channel not found.")
        return

    now = datetime.now(timezone.utc)
    since, before, label = parse_when(when, now)

    raw = await count_occurrences_all(ch, et, since, before)
    msg = f"{raw} {label_for_type(et)} counted for {label}"

    await interaction.followup.send(msg)


@client.event
async def on_ready():
    activity = discord.Activity(type=discord.ActivityType.watching, name="ur eggs")
    await client.change_presence(activity=activity)

    guild = discord.Object(id=GUILD_ID)
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)

    print(f"✅ Logged in as {client.user} — Commands synced")

async def main():
    async with client:
        await client.start(TOKEN)

asyncio.run(main())

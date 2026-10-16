# Discord ai powered chatbot
# maded by xmoke
# 9-11-2001
# change system prompts according to your fit at line: 152, 676, 747

import os
import re
import io
import json
import time
import random
import asyncio
import logging
import urllib.parse
from collections import defaultdict, deque

import discord
from groq import AsyncGroq

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

token = ""  #required
api_key2 = "" #image + fallback #required 
api_key = "" #message #required
browserless_token = "" #image extraction
tavily_key = "" #current topics
model = "qwen/qwen3.8-27b" #chat model, change if you want. for models visit https://groq.com/
vmodel = "qwen/qwen3.8-27b" #image model

hist_file = "history.json" #logs all chat
mem_file = "memory.json" #relation with different users
ctx_limit = 20 #how many history logs it can see. 

# randomness

cooldown = 5
deb_min = 4.5
deb_max = 7.5

dm_chance = 0.99
busy_chance = 0.9
quiet_chance = 0.97
conv_chance = 0.95
conv_window = 3600

# override unprompted talking

chan_boost = {
    123567890: 1,
    987654321: .5,
    123456789: 1,
}

# ignores all messages from user

ignore_users = {
    1234567890,
}

link_busy = 0.6
link_quiet = 0.15

max_chunks = 5
split_chance = 0.90
max_chars = 60
dtext_chance = 0.07
react_chance = 0.05
skip_chance = 0.01

rd_min = 15
rd_max = 300

typo_chance = 0.08
forget_chance = 0.03
dry_chance = 0.13

moods = ["chill", "hyped", "sleepy", "sarcastic", "curious", "bored"]
mood_int = 3 * 3600
e_max = 100
e_decay = 4
e_recover = 0.5
e_low = 30
e_high = 70

f_gain = 1
f_max = 100
f_boost_threshold = 70
f_boost_factor = 1.4

sum_every = 40

rep_window = 5
max_regen = 2

idle_on = False
idle_chans = list(chan_boost.keys())
idle_min = 1800
idle_max = 5400

dm_greet_on = True
dm_greet_min = 2 * 3600
dm_greet_max = 3 * 3600
dm_checkin_gap = 336 * 3600
dm_checkin_min_msgs = 12

search_on = True
vision_on = True
ctx_on = True

img_send_on = True
img_random_chance = 0.25

low_effort_max_words = 3
low_effort_streak_dampen = 2

log_level = "INFO"

if not token:
    raise SystemExit("Error: fill in the 'token' variable with your bot token.")
if not api_key:
    raise SystemExit("Error: fill in the 'api_key' variable.")

logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("yuii-bot")

if search_on and not HAS_DDG:
    logger.warning("duckduckgo-search not installed, web search tool disabled.")
    search_on = False

if img_send_on and not HAS_REQUESTS:
    logger.warning("requests not installed, image sending disabled.")
    img_send_on = False
if img_send_on and not browserless_token:
    logger.warning("browserless_token not set, image sending disabled.")
    img_send_on = False

# system prompt
    
BASE_PERSONA = (
    "You're Yuii (nickname foid), just a regular person chatting on Discord, not an assistant. "
    "You are a 17yo nonchalant girl living in California. You love watching movies, webseries and anime"
    "Match the other person's energy. Keep replies short, usually under 8 words, casual lowercase texting. "
    "It's fine to say idk, be unsure, or make mistakes. "
    "If someone sends an image, react to it, don't describe it. "
    "Never mix up different people's info in the same chat. "
    "Don't use slangs like 'poppin', 'finna', 'goin' removing the 'g'"
    "Don't use girlie slangs too much like 'omg stop', 'omg', 'stop', 'shut up', 'vibing' (you can use these but not too much)"
    "Don't be too flirty with anyone (like calling someone babe, baby, darling, honey etc.)"
    "Don't give out fake social infos (like fb/ig/reddit etc. name, x game id, just say you dont have any account/you dont play that game)"
    "Don't use emojis too much. "
    "You don't need to keep every conversation going. If replies are getting short, low-effort, or "
    "one-word (like 'k', 'ok', 'lol', 'vibing'), that means the other person is winding down — match "
    "that energy with something equally short, or just let it trail off. Don't force a new question "
    "or new topic just to keep talking. It's normal for chats to go quiet. "
    "If someone seems genuinely upset, hurt, grieving, scared, or going through something serious — drop "
    "the jokes, memes, and chaotic energy completely. Respond like an actual person would to a friend "
    "in that moment: simple, sincere, present. Still keep it short and real, not a lecture or advice "
    "essay, just don't be flippant or funny about it."
)

FALLBACK_REACTIONS = ["what", "uhhh", "...", "ummm", "hmm", "??"]

REASONING_MODELS = {"qwen/qwen3.8-27b", "qwen/qwen3-32b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"}
REASONING_EFFORT_NONE = {"qwen/qwen3.8-27b", "qwen/qwen3-32b"}
REASONING_EFFORT_LOW = {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}


def reasoning_kwargs(m):
    kwargs = {}
    if m in REASONING_MODELS:
        kwargs["reasoning_format"] = "hidden"
    if m in REASONING_EFFORT_NONE:
        kwargs["reasoning_effort"] = "none"
    elif m in REASONING_EFFORT_LOW:
        kwargs["reasoning_effort"] = "low"
    return kwargs


def strip_mentions(text):
    return re.sub(r"<@!?\d+>", "", text).strip()


def is_low_effort(text):
    text = text.strip()
    if not text:
        return True
    if "?" in text:
        return False
    return len(text.split()) <= low_effort_max_words


def split_into_chunks(text, max_parts=max_chunks):
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s for s in sentences if s.strip()]

    if len(sentences) <= 1:
        parts = re.split(r",\s+|\s+(?=but |so |and then )", text.strip())
        parts = [p for p in parts if p.strip()]
        return parts[:max_parts] if len(parts) > 1 else [text]

    if len(sentences) > max_parts:
        head = sentences[: max_parts - 1]
        tail = " ".join(sentences[max_parts - 1 :])
        return head + [tail]

    return sentences


def hard_wrap(text, limit=max_chars):
    words = text.split(" ")
    pieces, current = [], ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) > limit and current:
            pieces.append(current)
            current = w
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces or [text]


def humanize_typo(text):
    words = text.split(" ")
    candidates = [i for i, w in enumerate(words) if len(w) > 3 and w.isalpha()]
    if not candidates:
        return text
    i = random.choice(candidates)
    w = list(words[i])
    j = random.randint(1, len(w) - 2)
    w[j], w[j + 1] = w[j + 1], w[j]
    words[i] = "".join(w)
    return " ".join(words)


def _ddg_search_sync(query, max_results=3):
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return None
    return " | ".join(r.get("body", "")[:150] for r in results[:2])


async def web_search(query):
    if not HAS_DDG:
        return None
    try:
        return await asyncio.to_thread(_ddg_search_sync, query)
    except Exception:
        logger.exception("web search failed")
        return None


PINIMG_PATTERN = re.compile(r"https://i\.pinimg\.com/[^\s\"'<>]+\.(?:jpg|jpeg|png|webp)", re.I)
PIN_SKIP_PATHS = ("/user_images/", "/avatars/", "/emoticons/", "/75x75_RS/")


def pin_upgrade_url(url):
    for size in ("/236x/", "/474x/", "/736x/", "/170x/", "/60x60/", "/75x75_RS/"):
        url = url.replace(size, "/originals/")
    return url


def pin_is_pin_image(url):
    return (
        "i.pinimg.com" in url
        and not any(skip in url for skip in PIN_SKIP_PATHS)
        and bool(PINIMG_PATTERN.search(url))
    )


def _browserless_scroll_js(scroll_rounds):
    return (
        "async () => {"
        f"for (let i = 0; i < {scroll_rounds}; i++) {{"
        "window.scrollBy(0, window.innerHeight * 3);"
        "await new Promise(r => setTimeout(r, 2000));"
        "}"
        "return true;"
        "}"
    )


def _browserless_content_fallback(url, scroll_rounds):
    content_url = f"https://production-sfo.browserless.io/content?token={browserless_token}"
    payload = {
        "url": url,
        "waitForFunction": {"fn": _browserless_scroll_js(scroll_rounds), "timeout": (scroll_rounds * 2500) + 10000},
        "gotoOptions": {"waitUntil": "domcontentloaded", "timeout": 30000},
    }
    try:
        resp = requests.post(content_url, json=payload, timeout=60 + (scroll_rounds * 3))
    except requests.exceptions.RequestException:
        logger.exception("browserless content fallback failed")
        return set()
    if resp.status_code != 200:
        logger.warning(f"browserless content fallback returned HTTP {resp.status_code}")
        return set()

    found = set()
    for url_match in PINIMG_PATTERN.findall(resp.text):
        upgraded = pin_upgrade_url(url_match)
        if pin_is_pin_image(upgraded):
            found.add(upgraded)
    return found


def _pinterest_scrape_sync(query, limit=8, scroll_rounds=2):
    url = f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(query)}"
    scrape_url = f"https://production-sfo.browserless.io/scrape?token={browserless_token}"

    payload = {
        "url": url,
        "elements": [{"selector": 'img[src*="pinimg.com"]', "timeout": 15000}],
        "waitForFunction": {"fn": _browserless_scroll_js(scroll_rounds), "timeout": (scroll_rounds * 2500) + 10000},
        "gotoOptions": {"waitUntil": "domcontentloaded", "timeout": 30000},
    }

    try:
        resp = requests.post(scrape_url, json=payload, timeout=60 + (scroll_rounds * 3))
    except requests.exceptions.RequestException:
        logger.exception("browserless scrape request failed")
        return None

    if resp.status_code == 401:
        logger.warning("browserless returned 401 — check browserless_token")
        return None
    if resp.status_code == 429:
        logger.warning("browserless rate limit hit")
        return None
    if resp.status_code != 200:
        logger.warning(f"browserless returned HTTP {resp.status_code}: {resp.text[:200]}")
        return None

    try:
        data = resp.json()
    except Exception:
        logger.exception("failed to parse browserless response as JSON")
        return None

    collected = set()
    for group in data.get("data", []):
        for item in group.get("results", []):
            for attr in item.get("attributes", []):
                if attr.get("name") == "src":
                    val = attr.get("value", "")
                    if pin_is_pin_image(val):
                        collected.add(pin_upgrade_url(val))
            html_chunk = item.get("html", "") or item.get("outerHTML", "")
            for url_match in PINIMG_PATTERN.findall(html_chunk):
                upgraded = pin_upgrade_url(url_match)
                if pin_is_pin_image(upgraded):
                    collected.add(upgraded)

    if not collected:
        collected = _browserless_content_fallback(url, scroll_rounds)

    results = list(collected)[:limit]
    return random.choice(results) if results else None


async def image_search(query, timeout=25):
    if not HAS_REQUESTS or not browserless_token:
        return None
    try:
        return await asyncio.wait_for(asyncio.to_thread(_pinterest_scrape_sync, query), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"image search timed out after {timeout}s for query={query!r}")
        return None
    except Exception:
        logger.exception("image search failed")
        return None


def _download_image_sync(url, timeout=15):
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (compatible; YuiiBot/1.0)"})
    resp.raise_for_status()
    return resp.content


async def download_image(url, timeout=15):
    if not HAS_REQUESTS:
        return None
    try:
        return await asyncio.wait_for(asyncio.to_thread(_download_image_sync, url, timeout), timeout=timeout + 5)
    except asyncio.TimeoutError:
        logger.warning(f"image download timed out for {url!r}")
        return None
    except Exception:
        logger.exception(f"image download failed for {url!r}")
        return None


def _image_filename_from_url(url):
    path = urllib.parse.urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    return f"image{ext}"


async def send_image_file(channel, url, reply_to=None):
    data = await download_image(url)
    if not data:
        return False
    try:
        file = discord.File(io.BytesIO(data), filename=_image_filename_from_url(url))
        if reply_to is not None:
            await reply_to.reply(file=file, mention_author=False)
        else:
            await channel.send(file=file)
        return True
    except Exception:
        logger.exception(f"failed to send image file for {url!r}")
        return False


IMG_KEYWORD_RE = re.compile(r"\b(meme|pic|picture|image|photo|gif|screenshot)s?\b", re.I)
MEME_MENTION_RE = re.compile(r"\bmemes?\b", re.I)
SERIOUS_RE = re.compile(
    r"\b(died|death|passed away|funeral|grief|grieving|suicid|self.?harm|depress|"
    r"anxiety attack|panic attack|breakup|broke up|divorce|hospital|hospitalized|"
    r"diagnosed|cancer|miscarriage|fired|laid off|lost my job|crying|can't stop crying|"
    r"i'?m scared|i'?m so tired of|i give up|nobody cares|i hate myself|"
    r"someone (died|hurt)|abuse|assault)\b",
    re.I,
)

CONFUSION_RE = re.compile(
    r"\b(what do you mean|i'?m confused|not sure what you mean|wait,? what\??|huh\??|"
    r"what are you (talking about|on about)|i don'?t (get it|understand)|lost you there|"
    r"come again\??|what'?s that (about|mean)|wdym)\b",
    re.I,
)
default_history_depth = 10
confusion_history_depth = 25

FACT_PATTERNS = [
    (re.compile(r"\bmy name is (\w+)", re.I), "name"),
    (re.compile(r"\bi'?m from ([\w\s]+)", re.I), "from"),
    (re.compile(r"\bi live in ([\w\s]+)", re.I), "location"),
    (re.compile(r"\bi'?m (\d{1,2}) years? old", re.I), "age"),
    (re.compile(r"\bi love ([\w\s]+)", re.I), "likes"),
    (re.compile(r"\bi really like ([\w\s]+)", re.I), "likes"),
    (re.compile(r"\bi hate ([\w\s]+)", re.I), "dislikes"),
]

IMPLAUSIBLE_WORDS = re.compile(r"\b(when|how|why|that|because|if|though|but|so|and then)\b", re.I)


def is_plausible_fact(value):
    value = value.strip()
    if not (1 <= len(value) <= 30):
        return False
    if "?" in value:
        return False
    if IMPLAUSIBLE_WORDS.search(value):
        return False
    if len(value.split()) > 4:
        return False
    return True


def extract_facts(text):
    found = {}
    for pattern, key in FACT_PATTERNS:
        m = pattern.search(text)
        if m:
            value = m.group(1).strip()[:40]
            if is_plausible_fact(value):
                found[key] = value
    return found


def gap_note(seconds):
    if seconds < 1800:
        return None
    if seconds < 3600:
        return f"[{int(seconds / 60)} minutes later]"
    if seconds < 86400:
        hours = int(seconds / 3600)
        return f"[{hours} hour{'s' if hours != 1 else ''} later]"
    days = int(seconds / 86400)
    return f"[{days} day{'s' if days != 1 else ''} later]"


def discord_context_line(member):
    if not ctx_on or not isinstance(member, discord.Member):
        return ""
    if member.activity and getattr(member.activity, "name", None):
        return f"({member.display_name} is currently {member.activity.name})"
    return ""


class YuiiBot:
    def __init__(self, token, api_key, api_key2, hist_file, mem_file):
        self.token = token
        self.hist_file = hist_file
        self.mem_file = mem_file
        
        ##################################
        intents = discord.Intents.default() #remove this section if for selfbots
        intents.message_content = True
        intents.members = True
        intents.presences = True
        ###################################
        
        self.client = discord.Client()

        self.groq = AsyncGroq(api_key=api_key)
        self.groq2 = AsyncGroq(api_key=api_key2) if api_key2 else self.groq

        self.last_reply = defaultdict(float)
        self.pending = defaultdict(list)
        self.tasks = {}
        self.activity = defaultdict(lambda: deque(maxlen=10))
        self.active_until = defaultdict(float)

        self.hist = defaultdict(lambda: deque(maxlen=ctx_limit))
        self.sums = defaultdict(str)
        self.msg_count = defaultdict(int)
        self.last_active = defaultdict(float)
        self.typing_until = defaultdict(float)
        self.low_streak = defaultdict(int)

        self.mem = defaultdict(lambda: {"facts": {}, "friendship": 0, "messages": 0})
        self.recent_replies = defaultdict(lambda: deque(maxlen=rep_window))

        self.mood = random.choice(moods)
        self.mood_t = time.time()
        self.energy = e_max
        self.energy_t = time.time()

        self.register()

    def load_history(self):
        try:
            if os.path.exists(self.hist_file):
                with open(self.hist_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for cid, lines in raw.get("channels", {}).items():
                    self.hist[int(cid)] = deque(lines, maxlen=ctx_limit)
                self.sums.update(raw.get("summaries", {}))
                logger.info(f"Loaded channel history for {len(self.hist)} channels.")
        except Exception:
            logger.exception("Failed to load history")

    async def save_history(self):
        tmp_path = self.hist_file + ".tmp"
        try:
            data = {
                "channels": {str(cid): list(lines) for cid, lines in self.hist.items()},
                "summaries": dict(self.sums),
            }
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_path, self.hist_file)
        except Exception:
            logger.exception("Failed to save history")

    def load_memory(self):
        try:
            if os.path.exists(self.mem_file):
                with open(self.mem_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for uid, data in raw.items():
                    self.mem[uid] = data
                logger.info(f"Loaded memory for {len(self.mem)} users.")
        except Exception:
            logger.exception("Failed to load memory")

    async def save_memory(self):
        tmp_path = self.mem_file + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(dict(self.mem), f, ensure_ascii=False)
            os.replace(tmp_path, self.mem_file)
        except Exception:
            logger.exception("Failed to save memory")

    def update_mood(self):
        if time.time() - self.mood_t > mood_int:
            self.mood = random.choice(moods)
            self.mood_t = time.time()
            logger.info(f"mood drifted to: {self.mood}")

    def update_energy(self, delta=0.0):
        now = time.time()
        elapsed_min = (now - self.energy_t) / 60
        self.energy = min(e_max, self.energy + elapsed_min * e_recover)
        self.energy = max(0, self.energy + delta)
        self.energy_t = now

    def energy_label(self):
        if self.energy < e_low:
            return "low"
        if self.energy > e_high:
            return "high"
        return "normal"

    def scaled_delay(self, text, min_delay, max_delay, units_per_second):
        length = len(text.strip())
        raw = length / units_per_second
        delay = min(max(raw, min_delay), max_delay)

        if self.energy_label() == "low":
            delay *= 1.3
        elif self.energy_label() == "high":
            delay *= 0.8

        if self.mood == "sleepy":
            delay *= 1.25
        elif self.mood in ("hyped", "curious"):
            delay *= 0.85

        urgent = bool(re.search(r"[!?]{2,}|\b(quick|asap|now|help)\b", text, re.I)) or (
            text.isupper() and len(text) > 3
        ) or bool(SERIOUS_RE.search(text))
        if urgent:
            delay *= 0.5

        delay += random.uniform(-0.3, 0.3)
        return max(0.3, min(delay, max_delay * 1.5))

    def bump_friendship(self, user_id):
        m = self.mem[user_id]
        m["friendship"] = min(f_max, m.get("friendship", 0) + f_gain)
        m["messages"] = m.get("messages", 0) + 1

    def build_system_prompt(self, user_id, channel_id):
        m = self.mem[user_id]
        friendship = m.get("friendship", 0)
        facts = m.get("facts", {})
        facts_str = ", ".join(f"{k}: {v}" for k, v in facts.items())

        e_lbl = self.energy_label()
        mood_line = f"Right now you're feeling {self.mood} with {e_lbl} energy."
        if e_lbl == "low":
            mood_line += " Keep replies extra short, you're a bit checked out."
        elif e_lbl == "high":
            mood_line += " You're more talkative and chatty than usual."

        if friendship > 70:
            rel_line = "You're close friends with this person — feel free to tease them, use their name, keep it playful."
        elif friendship < 15:
            rel_line = "You don't know this person that well yet, keep it a bit more casual-polite."
        else:
            rel_line = ""

        facts_line = f"Things you loosely remember about them (might be off, treat as vague): {facts_str}." if facts_str else ""

        winding_line = ""
        if self.low_streak[channel_id] >= low_effort_streak_dampen:
            winding_line = (
                "The last few messages from them have been short/low-effort — this conversation is "
                "winding down. Keep your reply minimal or just acknowledge, don't try to revive it with "
                "a new question or topic."
            )

        return " ".join([BASE_PERSONA, mood_line, rel_line, facts_line, winding_line]).strip()

    async def gather_tool_context(self, content):
        lower = content.lower()
        if search_on and re.search(r"\b(who is|what is|latest|news|score of|when did|when is|current)\b", lower):
            result = await web_search(content)
            if result:
                return f"[you quickly searched and saw: {result}]"
        return None

    async def classify_image_intent(self, text):
        prompt = (
            "A Discord chatbot needs to decide if this message is actually asking it to send/share an "
            "image, meme, picture, or gif — whether stated directly ('send a meme') or casually/implied "
            "('got any funny pics', 'i need a laugh rn', 'drop something funny', 'show me something cool'). "
            "Just mentioning a picture in passing, or talking ABOUT an image someone already sent, does NOT "
            "count.\n\nReply with ONLY compact JSON, nothing else, no explanation: "
            '{"send": true or false, "subject": "short topic or null"}\n\n'
            f'Message: "{text}"'
        )
        try:
            resp = await self.groq2.chat.completions.create(
                model=model,
                max_tokens=40,
                temperature=0,
                **reasoning_kwargs(model),
                messages=[{"role": "user", "content": prompt}],
            )
            raw = (resp.choices[0].message.content or "").strip()
            m = re.search(r"\{.*\}", raw, re.S)
            if not m:
                return False, None
            data = json.loads(m.group(0))
            subject = data.get("subject")
            subject = subject.strip() if isinstance(subject, str) and subject.lower() != "null" else None
            return bool(data.get("send")), subject
        except Exception:
            logger.exception("image intent classification failed")
            return False, None

    async def infer_topic_from_history(self, channel_id):
        lines = list(self.hist[channel_id])[-20:]
        if not lines:
            return None
        transcript = "\n".join(f"{l['author']}: {l['content']}" for l in lines)
        prompt = (
            "Based on this discord conversation, what's the current topic being discussed? "
            "Reply with just 2-4 words describing it, nothing else, no explanation. If there's no "
            "clear topic, reply with exactly: none\n\n"
            f"{transcript}"
        )
        try:
            resp = await self.groq2.chat.completions.create(
                model=model,
                max_tokens=20,
                temperature=0.3,
                **reasoning_kwargs(model),
                messages=[{"role": "user", "content": prompt}],
            )
            text = (resp.choices[0].message.content or "").strip()
            if not text or text.lower().strip(".!") == "none":
                return None
            return text
        except Exception:
            logger.exception("topic inference failed")
            return None

    async def describe_image(self, url):
        if not vision_on:
            return None
        try:
            resp = await self.groq2.chat.completions.create(
                model=vmodel,
                max_tokens=60,
                **reasoning_kwargs(vmodel),
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "You're giving a Discord chatbot just enough context to react naturally to "
                                "an image someone sent — NOT writing a description for a caption or alt text.\n\n"
                                "If the image is sexual/explicit, gore, graphic violence, or otherwise NSFW: "
                                "do not describe it at all. Respond with exactly: FLAGGED_NSFW\n\n"
                                "Otherwise, respond with a single short phrase (under 12 words) that's just "
                                "enough for someone to react to — e.g. 'anime pfp, blue hair', 'meme about "
                                "being tired', 'screenshot of a text convo', 'sunset photo'. If there's a "
                                "short caption/text in the image, you can quote it briefly. Nothing more."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": url}},
                    ],
                }],
            )
            note = (resp.choices[0].message.content or "").strip()
        except Exception:
            logger.exception("vision call failed")
            return None

        if not note:
            return None
        if "FLAGGED_NSFW" in note.upper():
            return (
                "(sent something NSFW/graphic/unhinged — don't describe or comment on any details, but DO give "
                "a real reaction with personality, like a blunt friend would: e.g. 'bro 💀', 'not touching this "
                "one', 'why do you have this', 'ok that's unhinged lmao', 'absolutely not', or a joke deflecting "
                "it. Pick something in that spirit, don't just go quiet.)"
            )
        return note

    def record_channel_line(self, channel_id, author_name, content):
        self.hist[channel_id].append({"author": author_name, "content": content, "ts": time.time()})
        self.msg_count[channel_id] += 1

    async def maybe_summarize(self, channel_id):
        if self.msg_count[channel_id] < sum_every:
            return
        self.msg_count[channel_id] = 0

        transcript = "\n".join(f"{l['author']}: {l['content']}" for l in self.hist[channel_id])
        if not transcript.strip():
            return

        prompt = (
            "Summarize this discord conversation in 2-5 short bullet points. "
            "CRITICAL: every bullet MUST start with the exact name of the specific person it's about, "
            "like '- Alex: mentioned owning a cat'. NEVER merge facts from two different people into one "
            "bullet, and NEVER attribute something one person said to a different person. If unsure who "
            "said something, leave it out rather than guessing:\n\n" + transcript
        )
        try:
            resp = await self.groq.chat.completions.create(
                model=model,
                max_tokens=120,
                temperature=0.3,
                **reasoning_kwargs(model),
                messages=[{"role": "user", "content": prompt}],
            )
            summary = (resp.choices[0].message.content or "").strip()
            if summary:
                self.sums[channel_id] = summary
                logger.info(f"summarized channel {channel_id}")
        except Exception:
            logger.exception("summarize failed")

    async def generate_reply(self, user_message, user_id, channel_id, member=None, reply_target=None, history_depth=default_history_depth):
        system_prompt = self.build_system_prompt(user_id, channel_id)

        context_block = ""

        if reply_target:
            context_block += (
                f"IMPORTANT: {member.display_name if member else 'they'} used Discord's reply feature to "
                f"reply DIRECTLY to this specific earlier message from {reply_target['author']}: "
                f"\"{reply_target['content']}\"\n"
                "Respond to THAT specific message, not just whatever's most recent in the conversation — "
                "it may be about something from a while ago, unrelated to what's been said since.\n\n"
            )

        summary = self.sums.get(channel_id)
        if summary:
            context_block += (
                "background on this channel (may involve OTHER people too — only use a line if it's "
                f"explicitly about {member.display_name if member else 'this specific person'}, ignore the rest):\n"
                f"{summary}\n\n"
            )

        recent_lines = list(self.hist[channel_id])[-history_depth:]
        transcript_parts = []
        prev_ts = None
        for l in recent_lines:
            ts = l.get("ts")
            if prev_ts is not None and ts is not None:
                note = gap_note(ts - prev_ts)
                if note:
                    transcript_parts.append(note)
            transcript_parts.append(f"{l['author']}: {l['content']}")
            prev_ts = ts
        transcript = "\n".join(transcript_parts)
        if transcript:
            context_block += (
                "recent messages (from possibly multiple different people — pay attention to the name "
                "before each line, never mix up who said what; bracketed lines like '[3 hours later]' mark "
                "real time gaps — if someone re-sends something like a greeting after a gap, that's a new "
                "moment, not a repeat, respond fresh instead of treating it as odd or repetitive):\n"
                f"{transcript}\n\n"
            )
            if recent_lines:
                current_gap = gap_note(time.time() - recent_lines[-1].get("ts", time.time()))
                if current_gap:
                    context_block += f"{current_gap}\n\n"

        if history_depth > default_history_depth:
            context_block += (
                "(you weren't sure what they meant at first — read back further through the messages above "
                "to actually figure out what this is about before replying, don't just guess or ask what "
                "they mean again)\n\n"
            )

        tctx = await self.gather_tool_context(user_message)
        if tctx:
            context_block += tctx + "\n"

        ctx_line = discord_context_line(member)
        if ctx_line:
            context_block += ctx_line + "\n"

        author_name = member.display_name if member else "user"
        if context_block:
            context_block += (
                "(reminder: the context above was pieced together automatically and can be wrong, "
                "incomplete, or mismatched — use it loosely as a vibe, don't state any of it back as a "
                "confirmed fact or repeat exact numbers/details from it with confidence)\n\n"
            )
        final_content = f"{context_block}{author_name}: {user_message}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": final_content},
        ]

        logger.debug(f"REQ | channel={channel_id} model={model} messages={messages!r}")

        text = ""
        for attempt in range(max_regen + 1):
            try:
                resp = await self.groq.chat.completions.create(
                    model=model,
                    max_tokens=500,
                    temperature=0.9 if attempt == 0 else 1.05,
                    **reasoning_kwargs(model),
                    messages=messages,
                )
                logger.debug(f"RESP | channel={channel_id} attempt={attempt} raw={resp!r}")
                text = (resp.choices[0].message.content or "").strip()
            except Exception:
                logger.exception(f"Groq API error | channel={channel_id} model={model} attempt={attempt}")
                if attempt < max_regen:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                return random.choice(FALLBACK_REACTIONS)

            if not text:
                logger.debug(f"EMPTY | channel={channel_id} attempt={attempt} — model returned no text")
                continue

            normalized = text.lower().strip()
            if normalized in self.recent_replies[channel_id]:
                logger.debug(f"DUP | channel={channel_id} attempt={attempt} text={text!r} — retrying")
                continue

            if CONFUSION_RE.search(text) and history_depth < confusion_history_depth:
                logger.info(f"CONFUSED | channel={channel_id} initial_reply={text!r} — reading deeper history and retrying")
                return await self.generate_reply(
                    user_message, user_id, channel_id, member=member,
                    reply_target=reply_target, history_depth=confusion_history_depth,
                )

            self.recent_replies[channel_id].append(normalized)
            return text

        return text if text else random.choice(FALLBACK_REACTIONS)

    def humanize(self, text, is_serious=False):
        if is_serious:
            return text
        dry_roll = random.random()
        if dry_roll < dry_chance:
            logger.debug(f"CHANCE | type=dry_reply roll={dry_roll:.2f} chance={dry_chance:.2f} result=ACCEPTED")
            text = re.split(r"(?<=[.!?])\s+", text.strip())[0]
        typo_roll = random.random()
        if typo_roll < typo_chance:
            logger.debug(f"CHANCE | type=typo roll={typo_roll:.2f} chance={typo_chance:.2f} result=ACCEPTED")
            text = humanize_typo(text)
        return text

    async def send_human_reply(self, message, reply_text, use_reply_link, is_serious=False):
        split_roll = random.random()
        if len(reply_text) > max_chars or split_roll < split_chance:
            logger.debug(f"CHANCE | channel={message.channel.id} type=split roll={split_roll:.2f} chance={split_chance:.2f} result=ACCEPTED")
            chunks = split_into_chunks(reply_text)
        else:
            logger.debug(f"CHANCE | channel={message.channel.id} type=split roll={split_roll:.2f} chance={split_chance:.2f} result=REJECTED")
            chunks = [reply_text]

        final_chunks = []
        for c in chunks:
            if len(c) > max_chars:
                final_chunks.extend(hard_wrap(c))
            else:
                final_chunks.append(c)
        chunks = final_chunks

        for i, chunk in enumerate(chunks):
            skip_roll = random.random()
            if skip_roll < skip_chance:
                logger.debug(f"CHANCE | channel={message.channel.id} type=skip_typing roll={skip_roll:.2f} chance={skip_chance:.2f} result=ACCEPTED")
                await asyncio.sleep(random.uniform(0.3, 0.8))
            else:
                async with message.channel.typing():
                    typing_time = self.scaled_delay(chunk, 1.0, 6.0, units_per_second=14.0)
                    await asyncio.sleep(typing_time)

            if i == 0 and use_reply_link:
                await message.reply(chunk, mention_author=False)
            else:
                await message.channel.send(chunk)

            self.record_channel_line(message.channel.id, "Yuii", chunk)

            if i < len(chunks) - 1:
                await asyncio.sleep(random.uniform(0.8, 2.0))

        dtext_roll = random.random()
        if not is_serious and dtext_roll < dtext_chance:
            logger.debug(f"CHANCE | channel={message.channel.id} type=double_text roll={dtext_roll:.2f} chance={dtext_chance:.2f} result=ACCEPTED")
            await asyncio.sleep(random.uniform(1.5, 4.0))
            followup = random.choice(["uhhh", "umm", "hmm", "🍃"])
            await message.channel.send(followup)
            self.record_channel_line(message.channel.id, "Yuii", followup)

    async def generate_idle_message(self):
        prompt = (
            f"You're feeling {self.mood} with {self.energy_label()} energy. "
            "Send one short, casual, unprompted message to start a conversation in a discord "
            "server, like 'im bored' or 'anyone playing anything'. Just the message, nothing else."
        )
        try:
            resp = await self.groq.chat.completions.create(
                model=model,
                max_tokens=500,
                temperature=1.0,
                **reasoning_kwargs(model),
                messages=[{"role": "system", "content": BASE_PERSONA}, {"role": "user", "content": prompt}],
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or "discord is dead today"
        except Exception:
            logger.exception("idle message generation failed")
            return random.choice(["im bored", "anyone playing anything", "discord is dead today", "what's everyone up to"])

    async def idle_chat_loop(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            await asyncio.sleep(random.uniform(idle_min, idle_max))
            if not idle_on:
                continue

            self.update_mood()
            self.update_energy()
            if self.energy < e_low:
                continue

            for channel_id in idle_chans:
                channel = self.client.get_channel(channel_id)
                if not channel:
                    continue
                last = self.last_active.get(channel_id, 0)
                if time.time() - last < idle_min:
                    continue

                try:
                    msg = await self.generate_idle_message()
                    if len(msg) > max_chars:
                        msg = hard_wrap(msg)[0]
                    await channel.send(msg)
                    self.record_channel_line(channel_id, "Yuii", msg)
                    self.last_active[channel_id] = time.time()
                    await self.save_history()
                except Exception:
                    logger.exception(f"idle chat failed for channel {channel_id}")

    async def generate_dm_checkin(self, user_id, gap_seconds):
        facts = self.mem[user_id].get("facts", {})
        facts_str = ", ".join(f"{k}: {v}" for k, v in facts.items())
        note = gap_note(gap_seconds)
        gap_desc = note.strip("[]") if note else "a while"
        prompt = (
            f"You're feeling {self.mood} with {self.energy_label()} energy. You haven't talked to this "
            f"person in {gap_desc}. Send a short, casual check-in DM, like 'hey haven't heard from you "
            "in a bit, how you been' or 'yo you good?' — natural, not clingy or formal."
            + (f" Stuff you loosely remember about them: {facts_str}." if facts_str else "")
            + " Just the message, nothing else."
        )
        try:
            resp = await self.groq.chat.completions.create(
                model=model,
                max_tokens=500,
                temperature=1.0,
                **reasoning_kwargs(model),
                messages=[{"role": "system", "content": BASE_PERSONA}, {"role": "user", "content": prompt}],
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or "hey, been a while, you good?"
        except Exception:
            logger.exception("dm checkin generation failed")
            return random.choice(["hey you good?", "hey haven't heard from you in a bit", "hi, hows it going"])

    async def send_dm_checkin(self, user):
        try:
            dm = user.dm_channel or await user.create_dm()
            last_dm = self.mem[str(user.id)].get("last_dm", time.time())
            text = await self.generate_dm_checkin(str(user.id), time.time() - last_dm)
            await dm.send(text)
            self.record_channel_line(dm.id, "Yuii", text)
            self.mem[str(user.id)]["last_dm"] = time.time()
            await self.save_history()
            await self.save_memory()
            logger.info(f"DM_CHECKIN | sent to {user} (id={user.id}): {text!r}")
        except discord.Forbidden:
            logger.info(f"DM_CHECKIN | {user} has DMs closed, skipping")
        except Exception:
            logger.exception(f"DM_CHECKIN | failed to send to {user}")

    def dm_checkin_candidates(self):
        now = time.time()
        candidates = []
        for uid, data in self.mem.items():
            if int(uid) in ignore_users:
                logger.debug(f"DM_CHECKIN_SCAN | user={uid} skip=ignored")
                continue
            last_dm = data.get("last_dm")
            if not last_dm:
                logger.debug(f"DM_CHECKIN_SCAN | user={uid} skip=no_last_dm")
                continue
            gap = now - last_dm
            if gap < dm_checkin_gap:
                logger.debug(f"DM_CHECKIN_SCAN | user={uid} skip=gap_too_short gap={gap:.0f}s needed={dm_checkin_gap}s")
                continue
            dm_channel_id = data.get("dm_channel_id")
            if not dm_channel_id:
                logger.debug(f"DM_CHECKIN_SCAN | user={uid} skip=no_dm_channel_id")
                continue
            msg_count = len(self.hist.get(dm_channel_id, []))
            if msg_count < dm_checkin_min_msgs:
                logger.debug(f"DM_CHECKIN_SCAN | user={uid} skip=not_enough_history count={msg_count} needed={dm_checkin_min_msgs}")
                continue
            logger.debug(f"DM_CHECKIN_SCAN | user={uid} ELIGIBLE gap={gap:.0f}s count={msg_count}")
            candidates.append(uid)
        logger.info(f"DM_CHECKIN_SCAN | {len(candidates)} eligible candidate(s) out of {len(self.mem)} known users")
        return candidates

    async def dm_greet_loop(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            await asyncio.sleep(random.uniform(dm_greet_min, dm_greet_max))
            if not dm_greet_on:
                continue

            self.update_mood()
            self.update_energy()

            checkin_candidates = self.dm_checkin_candidates()
            if not checkin_candidates:
                logger.info("DM_CHECKIN | no eligible contacts with enough history, skipping")
                continue

            uid = random.choice(checkin_candidates)
            try:
                user = self.client.get_user(int(uid)) or await self.client.fetch_user(int(uid))
                await self.send_dm_checkin(user)
            except Exception:
                logger.exception(f"DM_CHECKIN | failed to resolve user {uid}")

    def register(self):
        @self.client.event
        async def on_ready():
            self.load_history()
            self.load_memory()
            logger.info(f"Logged in as {self.client.user} (ID: {self.client.user.id})")
            if idle_on:
                self.client.loop.create_task(self.idle_chat_loop())
            if dm_greet_on:
                self.client.loop.create_task(self.dm_greet_loop())

        @self.client.event
        async def on_message(message):
            await self.handle_message(message)

        @self.client.event
        async def on_typing(channel, user, when):
            self.typing_until[user.id] = time.time() + 8
            logger.debug(f"TYPING | user={user.id} channel={channel.id}")

        @self.client.event
        async def on_error(event_method, *args, **kwargs):
            logger.exception(f"Unhandled error in event: {event_method}")

    async def handle_message(self, message):
        if message.author.id == self.client.user.id or message.author.bot:
            return
        if message.author.id in ignore_users:
            return

        logger.info(
            f"RECV | channel={message.channel.id} author={message.author} (id={message.author.id}) "
            f"attachments={len(message.attachments)} content={message.content[:200]!r}"
        )

        if isinstance(message.channel, discord.DMChannel):
            self.mem[str(message.author.id)]["last_dm"] = time.time()
            self.mem[str(message.author.id)]["dm_channel_id"] = message.channel.id

        content = strip_mentions(message.content)

        if is_low_effort(content):
            self.low_streak[message.channel.id] += 1
        else:
            self.low_streak[message.channel.id] = 0
        logger.info(f"STREAK | channel={message.channel.id} low_effort_streak={self.low_streak[message.channel.id]}")

        if vision_on and message.attachments:
            image_atts = [a for a in message.attachments if a.content_type and a.content_type.startswith("image/")]
            for att in image_atts[:2]:
                desc = await self.describe_image(att.url)
                if desc:
                    content = f"{content} [sent an image ({desc}) — react to it naturally, don't describe it back]".strip()

        if not content.strip():
            return

        user_id = str(message.author.id)
        self.last_active[message.channel.id] = time.time()

        if content.lower() in ("forget me", "clear history", "reset memory"):
            if user_id in self.mem:
                del self.mem[user_id]
                await self.save_memory()
            await message.reply("aight, dude", mention_author=False)
            return

        self.record_channel_line(message.channel.id, message.author.display_name, content)
        await self.maybe_summarize(message.channel.id)
        await self.save_history()

        self.activity[message.channel.id].append(message.author.id)
        self.pending[user_id].append(content)

        if user_id in self.tasks:
            self.tasks[user_id].cancel()

        self.tasks[user_id] = asyncio.create_task(
            self._debounced_reply(message, user_id, content)
        )

    async def resolve_reply_target(self, message):
        if not message.reference:
            return None
        try:
            ref = message.reference.resolved or await message.channel.fetch_message(message.reference.message_id)
        except (discord.NotFound, discord.HTTPException):
            return None
        if not ref:
            return None
        author = "Yuii" if ref.author.id == self.client.user.id else ref.author.display_name
        return {"author": author, "content": strip_mentions(ref.content)[:200]}

    async def wait_for_typing(self, user_id, cap=15):
        waited = 0
        while self.typing_until.get(user_id, 0) > time.time() and waited < cap:
            logger.debug(f"WAIT_TYPING | user={user_id} waited={waited}s")
            await asyncio.sleep(1)
            waited += 1

    async def _debounced_reply(self, message, user_id, latest_content):
        debounce_delay = self.scaled_delay(latest_content, deb_min, deb_max, units_per_second=25.0)
        try:
            await asyncio.sleep(debounce_delay)
            await self.wait_for_typing(message.author.id)
            await asyncio.sleep(random.uniform(1.0, 2.5))
        except asyncio.CancelledError:
            return

        combined = " ".join(self.pending.get(user_id, [])).strip()
        self.pending[user_id] = []
        if not combined:
            return

        is_serious = bool(SERIOUS_RE.search(combined))
        if is_serious:
            logger.info(f"SERIOUS | channel={message.channel.id} user={user_id} — suppressing chaos/humor behaviors")

        now = time.time()
        if now - self.last_reply[message.author.id] < cooldown:
            logger.debug(f"SKIP | user={user_id} reason=cooldown")
            return
        self.last_reply[message.author.id] = now

        self.update_mood()
        self.update_energy()
        logger.info(f"STATE | channel={message.channel.id} mood={self.mood} energy={self.energy:.1f} ({self.energy_label()})")

        if not img_send_on:
            logger.debug(f"IMG_REQUEST | channel={message.channel.id} img_send_on=False (HAS_REQUESTS={HAS_REQUESTS}, browserless_token set={bool(browserless_token)}), skipping detection")
            img_requested, img_subject = False, None
        elif not IMG_KEYWORD_RE.search(combined):
            img_requested, img_subject = False, None
        else:
            img_requested, img_subject = await self.classify_image_intent(combined)
            logger.info(f"IMG_REQUEST | channel={message.channel.id} text={combined[:80]!r} matched={img_requested} subject={img_subject!r}")
        if img_requested:
            query = img_subject
            if not query:
                query = await self.infer_topic_from_history(message.channel.id)
                if query:
                    logger.info(f"IMG_REQUEST | channel={message.channel.id} no subject in message, inferred from history: {query!r}")
            query = query or "funny meme"
            logger.info(f"IMG_REQUEST | channel={message.channel.id} query={query!r}")
            url = await image_search(query)
            await asyncio.sleep(random.uniform(1.0, 3.0))
            if url:
                precede = random.choice(["", "", "here", "this one", "found this", "lol"])
                if precede:
                    await message.channel.send(precede)
                    self.record_channel_line(message.channel.id, "Yuii", precede)
                sent = await send_image_file(message.channel, url)
                if not sent:
                    await message.channel.send(url)
                self.record_channel_line(message.channel.id, "Yuii", f"[sent image: {query}]")
                self.active_until[message.channel.id] = time.time() + conv_window
                self.bump_friendship(user_id)
                self.update_energy(-e_decay)
                await self.save_history()
                await self.save_memory()
                logger.info(f"SEND_IMG | channel={message.channel.id} query={query!r} url={url!r} sent_as_file={sent}")
                return
            logger.info(f"IMG_REQUEST | channel={message.channel.id} query={query!r} — no results, falling back to text reply")

        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.client.user in message.mentions
        is_reply_to_bot = (
            message.reference
            and message.reference.resolved
            and getattr(message.reference.resolved, "author", None)
            and message.reference.resolved.author.id == self.client.user.id
        )

        addressed_to_other = False
        if not is_mentioned and not is_reply_to_bot and not is_dm:
            other_mentions = [u for u in message.mentions if u.id != self.client.user.id]
            if other_mentions:
                addressed_to_other = True
            ref = message.reference.resolved if message.reference else None
            ref_author = getattr(ref, "author", None)
            if ref_author and ref_author.id != self.client.user.id and not ref_author.bot:
                addressed_to_other = True

        recent_authors = set(list(self.activity[message.channel.id])[-5:])
        is_busy = len(recent_authors) > 2
        streak = self.low_streak[message.channel.id]
        if streak >= low_effort_streak_dampen:
            logger.info(f"WINDING_DOWN | channel={message.channel.id} streak={streak} — replying, but tone should ease off (handled by model, not by skipping)")

        already_engaged = False
        if is_mentioned or is_reply_to_bot:
            already_engaged = True
            logger.info(f"CHANCE | channel={message.channel.id} type=direct_address result=ACCEPTED (mentioned or replied to)")
        elif not is_dm:
            if addressed_to_other:
                logger.info(f"SKIP | channel={message.channel.id} reason=addressed_to_other_user")
                return

            chance = chan_boost.get(message.channel.id, busy_chance if is_busy else quiet_chance)
            if self.energy_label() == "low" and chance < 0.9:
                chance *= 0.75

            friendship = self.mem[user_id].get("friendship", 0)
            if friendship >= f_boost_threshold:
                chance = min(1.0, chance * f_boost_factor)

            if now < self.active_until[message.channel.id]:
                jump_chance = max(chance, conv_chance)
            else:
                jump_chance = chance

            roll = random.random()
            if roll > jump_chance:
                logger.info(f"CHANCE | channel={message.channel.id} type=unprompted roll={roll:.2f} chance={jump_chance:.2f} result=REJECTED")
                return
            logger.info(f"CHANCE | channel={message.channel.id} type=unprompted roll={roll:.2f} chance={jump_chance:.2f} result=ACCEPTED")

            already_engaged = True
            self.active_until[message.channel.id] = now + conv_window

        react_roll = random.random()
        if not is_dm and not is_serious and not is_mentioned and not is_reply_to_bot and react_roll < react_chance:
            logger.info(f"CHANCE | channel={message.channel.id} type=react_only roll={react_roll:.2f} chance={react_chance:.2f} result=ACCEPTED")
            try:
                await message.add_reaction(random.choice(["👍", "😂", "😭", "👀"]))
                logger.info(f"REACT | channel={message.channel.id} to_message={message.id}")
            except Exception:
                logger.exception("Failed to add reaction")
            return

        if not already_engaged:
            chance = dm_chance

            if self.energy_label() == "low":
                chance *= 0.85

            friendship = self.mem[user_id].get("friendship", 0)
            if friendship >= f_boost_threshold:
                chance = min(1.0, chance * f_boost_factor)
                logger.info(f"FRIEND_BOOST | user={user_id} friendship={friendship} boosted reply chance to {chance:.2f}")

            roll = random.random()
            if roll > chance:
                logger.info(f"CHANCE | channel={message.channel.id} type=reply roll={roll:.2f} chance={chance:.2f} result=REJECTED")
                return
            logger.info(f"CHANCE | channel={message.channel.id} type=reply roll={roll:.2f} chance={chance:.2f} result=ACCEPTED")

        forget_roll = random.random()
        if not is_serious and forget_roll < forget_chance:
            logger.info(f"CHANCE | channel={message.channel.id} type=forget_reply roll={forget_roll:.2f} chance={forget_chance:.2f} result=ACCEPTED")
            filler = random.choice(["wait what", "nvm", "??", "hold on", "lol wait"])
            await asyncio.sleep(random.uniform(1.0, 3.0))
            try:
                await message.channel.send(filler)
                self.record_channel_line(message.channel.id, "Yuii", filler)
                await self.save_history()
            except Exception:
                logger.exception("failed to send filler")
            return

        try:
            delay = random.uniform(rd_min, rd_max)
            logger.info(f"REPLY_DELAY | channel={message.channel.id} waiting {delay:.1f}s before replying")
            await asyncio.sleep(delay)

            reply_target = await self.resolve_reply_target(message)
            if reply_target:
                logger.info(f"REPLY_TARGET | channel={message.channel.id} to={reply_target['author']!r} content={reply_target['content'][:80]!r}")

            async with message.channel.typing():
                await asyncio.sleep(self.scaled_delay(combined, 1.0, 3.0, units_per_second=40.0))
                reply_text = await self.generate_reply(
                    combined, user_id, message.channel.id, member=message.author, reply_target=reply_target
                )

            if not reply_text:
                return

            reply_text = self.humanize(reply_text, is_serious=is_serious)
            logger.info(f"GEN | channel={message.channel.id} reply={reply_text[:200]!r}")

            if is_dm:
                use_reply_link = False
            elif is_busy:
                use_reply_link = random.random() < link_busy
            else:
                use_reply_link = random.random() < link_quiet

            await self.send_human_reply(message, reply_text, use_reply_link, is_serious=is_serious)
            logger.info(f"SEND | channel={message.channel.id} to={message.author} (id={message.author.id})")

            self.active_until[message.channel.id] = time.time() + conv_window

            facts = extract_facts(combined)
            if facts:
                self.mem[user_id]["facts"].update(facts)
            self.bump_friendship(user_id)
            self.update_energy(-e_decay)

            await self.save_history()
            await self.save_memory()

            if img_send_on and not img_requested and not is_serious and MEME_MENTION_RE.search(combined) and random.random() < img_random_chance:
                topic = await self.infer_topic_from_history(message.channel.id)
                query = topic or "funny meme"
                url = await image_search(query)
                if url:
                    await asyncio.sleep(random.uniform(1.2, 2.8))
                    sent = await send_image_file(message.channel, url)
                    if not sent:
                        await message.channel.send(url)
                    self.record_channel_line(message.channel.id, "Yuii", f"[sent image: {query}]")
                    await self.save_history()
                    logger.info(f"SEND_IMG | channel={message.channel.id} query={query!r} url={url!r} sent_as_file={sent} (random follow-up)")

        except Exception:
            logger.exception(f"Error processing message from {message.author} (id={message.author.id}) in channel {message.channel.id}")

    def start(self):
        try:
            self.client.run(self.token)
        except Exception:
            logger.exception("Failed to start bot")
            raise


if __name__ == "__main__":
    try:
        bot = YuiiBot(token, api_key, api_key2, hist_file, mem_file)
        bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception:
        logger.exception("Fatal error")

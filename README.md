# Yuii

A single-file Discord bot that talks like a regular person instead of an assistant. It matches the energy of whoever it's talking to, keeps its replies short and split into small messages, has moods and energy levels, remembers people it talks to, and can send images and check in on people it has chatted with in DMs.

Runs on Groq's API. No `.env` file, everything is a plain variable at the top of `main.py`.

---

## Contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Setup](#setup)
4. [Running it](#running-it)
5. [User guide (for people chatting with the bot)](#user-guide-for-people-chatting-with-the-bot)
6. [Admin guide (for whoever runs it)](#admin-guide-for-whoever-runs-it)
7. [Configuration reference](#configuration-reference)
8. [Logs](#logs)
9. [Troubleshooting](#troubleshooting)
10. [Notes and limits](#notes-and-limits)

---

## Features

**Conversation**
- Replies in short, casual, lowercase messages, usually split into several small ones
- Matches the other person's energy and backs off when replies get short or low effort
- Drops the jokes and chaos automatically when someone seems upset or is dealing with something serious
- Understands Discord's reply feature, so it knows which message you are answering
- Reads the room: messages are timestamped, so a "good morning" the next day isn't treated as a repeat
- Waits until you stop typing before replying, and takes a random 15 to 300 seconds to answer, like a person who isn't glued to their phone
- If it doesn't understand a message, it re-reads more of the chat history and tries again

**Personality and memory**
- Moods that drift every few hours and an energy meter that drains with each reply
- Remembers basic facts people mention (name, location, likes, dislikes) and builds a friendship score that changes how it talks to them
- Periodic per-person summaries of each channel so older context isn't lost

**Images**
- Reacts to images people send (it never describes NSFW or graphic images, it just reacts)
- Sends images or memes on request, downloaded and attached as real files, using Pinterest results through Browserless
- Occasionally follows up a conversation about memes with one

**Other**
- Web search through DuckDuckGo for "who is / what is / latest / news" style questions
- Sends a casual check-in DM to people it has had a real DM conversation with, after a long silence
- Optional idle chat (off by default)
- An ignore list for users it should never respond to

---

## Requirements

- Python 3.10 or newer
- A Discord application with a bot token
- A [Groq](https://console.groq.com) API key (free tier works). A second key is optional
- A [Browserless](https://www.browserless.io) API key, only if you want image sending
- A [Tavily](https://tavily.com) API key is reserved in the config but not used by the current version

Install dependencies:

```bash
pip install discord.py groq duckduckgo-search requests
```

Or from the included file:

```bash
pip install -r requirements.txt
```

`duckduckgo-search` and `requests` are optional. If they are missing, web search and image sending turn themselves off with a warning in the logs.

---

## Setup

### 1. Create the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Open the **Bot** tab, create the bot, and copy its token.
3. Under **Privileged Gateway Intents**, enable **Message Content Intent** and **Server Members Intent**. The bot cannot read what people say without the first one.
4. Under **OAuth2 > URL Generator**, select the `bot` scope with permissions to read messages, send messages, attach files, add reactions, and read message history. Open the generated link to invite the bot to your server.

### 2. Get your API keys

- **Groq:** create a key at console.groq.com/keys. If you want to spread rate limits, make a second key on the same account and use it as `api_key2`.
- **Browserless (optional):** create an account and copy your API token. Without it, image sending is disabled.

### 3. Fill in the variables

Open `main.py` and set these near the top:

```python
token = "your_discord_bot_token"
api_key = "your_groq_api_key"
api_key2 = ""                      # optional second Groq key
browserless_token = ""             # optional, needed for sending images
tavily_key = ""                    # reserved, not used yet
```

`api_key2` handles the lighter background calls (deciding whether someone is asking for an image, reading images, guessing the topic of a chat). If you leave it empty, those calls share `api_key`.

**Keep your keys private.** They sit in plain text in this file. Don't commit it to a public repository or paste it into chats or screenshots. If a key is ever exposed, regenerate it.

### 4. Set up channels and users (optional)

```python
chan_boost = {
    123456789012345678: 1,    # channel ID: how eager the bot is there (0 to 1)
}

ignore_users = {
    987654321098765432,       # user IDs the bot will never respond to or DM
}
```

To get an ID, turn on Developer Mode in Discord (User Settings > Advanced), then right-click a channel or user and choose **Copy ID**.

---

## Running it

```bash
python main.py
```

Leave it running. It creates two files next to `main.py` as it goes:

- `history.json` recent messages per channel plus channel summaries
- `memory.json` per-person facts, friendship scores and DM tracking

Both are safe to delete if you want a fresh start.

---

## User guide (for people chatting with the bot)

**Talking to it**
- Mention it, reply to one of its messages, or DM it. It will answer.
- In channels it is active in, it also joins in on its own, but not when you are clearly talking to someone else (mentioning another person or replying to their message).
- Don't expect instant answers. It deliberately waits between 15 seconds and 5 minutes before replying, and shows a typing indicator once it starts writing.
- If you send several messages in a row, it waits for you to finish and answers them together.

**Asking for images**
- Ask naturally: "send me a funny cat meme", "got any pics of sunsets?", "drop a meme about mondays". If you don't say what kind, it picks a topic from the recent conversation.
- It sends the image as a file attachment. If the image can't be downloaded, it falls back to posting the link.
- Sending images only works if the person running the bot has set up Browserless.

**Sending it images**
- It reacts to what you send instead of describing it. If an image is explicit or graphic, it gives a short reaction and doesn't describe it.

**Tone**
- It matches your energy. Short replies from you get short replies back, and it won't force the chat to continue.
- If you tell it something heavy, like a loss, a breakup or a scary situation, it stops joking and responds more simply and sincerely.

**Privacy**
- To make it forget everything it has stored about you, send exactly one of these: `forget me`, `clear history` or `reset memory`.
- Note that this clears the facts and friendship data it has about you. Recent chat lines already saved in `history.json` are not removed by it.

**DM check-ins**
- If you have had a real DM conversation with it (at least 12 messages) and then gone quiet for a long time (14 days by default), it may send you a casual "hey, how have you been" DM. It won't cold-DM people it has never talked to.
- To stop this, ask the person running the bot to add your user ID to `ignore_users`.

---

## Admin guide (for whoever runs it)

**Making the bot more or less talkative in a channel**
Set the channel's value in `chan_boost`. `1` means it almost always joins in, `0.5` means about half the time. Channels not listed use `busy_chance` and `quiet_chance`, depending on how many people are talking.

**Blocking a user completely**
Add their ID to `ignore_users`. Their messages are skipped before anything else happens, and they are excluded from check-ins.

**Changing how fast it answers**
`rd_min` and `rd_max` (seconds) control the main reply delay. Set both low (for example `2` and `8`) for near-instant replies. `deb_min` and `deb_max` control how long it waits to batch up several quick messages.

**Changing how often it checks in on DM contacts**
- `dm_checkin_gap` how long someone must have been silent, in seconds (default 336 hours, 14 days)
- `dm_checkin_min_msgs` how many messages of DM history they need (default 12)
- `dm_greet_min` and `dm_greet_max` how often the bot looks for someone to check in on (default every 2 to 3 hours)
- `dm_greet_on = False` turns check-ins off entirely

The silence gap is measured from the last time the person sent a **DM**. Talking to the bot in a server does not reset it.

**Letting it start conversations**
Set `idle_on = True`. It will post an unprompted message in the channels in `idle_chans` when they've been quiet. Off by default.

**Turning features off**
`search_on`, `vision_on`, `img_send_on` and `ctx_on` can each be set to `False`.

**Changing the personality**
Edit `BASE_PERSONA`. This is the main prompt: name, age, interests, and style rules. Keep it fairly short, as very long prompts tend to make replies worse.

**Model changes**
`model` and `vmodel` set the Groq models for chat and for image reading. Groq retires models regularly. If you see `model_decommissioned` in the logs, check console.groq.com/docs/deprecations for the replacement and update those two variables. If the new model shows its reasoning in chat, add it to the `REASONING_MODELS` set near the top of the file.

---

## Configuration reference

Everything below is a variable at the top of `main.py`.

| Variable | What it does |
|---|---|
| `token` | Discord bot token |
| `api_key`, `api_key2` | Groq keys (second is optional) |
| `browserless_token` | Enables image sending |
| `tavily_key` | Reserved, unused |
| `model`, `vmodel` | Groq models for chat and for reading images |
| `hist_file`, `mem_file` | Where history and memory are saved |
| `ctx_limit` | How many recent lines per channel are kept for context |
| `cooldown` | Minimum seconds between replies to the same person |
| `deb_min`, `deb_max` | Wait to batch quick consecutive messages |
| `rd_min`, `rd_max` | Random reply delay range, in seconds |
| `dm_chance` | Reply chance in DMs |
| `busy_chance`, `quiet_chance` | Join-in chance in busy or quiet channels |
| `conv_chance`, `conv_window` | Chance and duration of staying engaged once a conversation starts |
| `chan_boost` | Per-channel join-in chance |
| `ignore_users` | User IDs to ignore completely |
| `link_busy`, `link_quiet` | Chance of using Discord's reply link in busy or quiet chats |
| `max_chunks`, `split_chance`, `max_chars` | How replies are split into small messages |
| `dtext_chance` | Chance of a quick follow-up message |
| `react_chance` | Chance of only reacting with an emoji |
| `skip_chance` | Chance of skipping the typing indicator |
| `typo_chance`, `forget_chance`, `dry_chance` | Chance of a typo, a "wait what" style filler, or a one-line dry reply |
| `moods`, `mood_int` | Possible moods and how often they change |
| `e_max`, `e_decay`, `e_recover`, `e_low`, `e_high` | Energy meter settings |
| `f_gain`, `f_max`, `f_boost_threshold`, `f_boost_factor` | Friendship score and the reply-chance boost for close friends |
| `sum_every` | Messages between channel summaries |
| `rep_window`, `max_regen` | Repeat-avoidance window and retry count |
| `idle_on`, `idle_chans`, `idle_min`, `idle_max` | Unprompted chat |
| `dm_greet_on`, `dm_greet_min`, `dm_greet_max` | DM check-in loop |
| `dm_checkin_gap`, `dm_checkin_min_msgs` | Who qualifies for a check-in |
| `search_on`, `vision_on`, `ctx_on` | Web search, image reading, Discord activity awareness |
| `img_send_on`, `img_random_chance` | Image sending and chance of a random meme follow-up |
| `low_effort_max_words`, `low_effort_streak_dampen` | What counts as a low-effort message and how many in a row mean the chat is winding down |
| `log_level` | `"INFO"` or `"DEBUG"` |

---

## Logs

Set `log_level = "DEBUG"` for the full picture. Every line is tagged:

| Tag | Meaning |
|---|---|
| `RECV` | A message came in |
| `STATE` | Current mood and energy |
| `CHANCE` | A random roll, with the roll, the threshold and whether it passed |
| `SKIP` | It chose not to reply, and why |
| `REPLY_DELAY` | How long it will wait before answering |
| `GEN` | The reply that was generated |
| `SEND` | The reply was sent |
| `IMG_REQUEST`, `SEND_IMG` | Image request detection and sending |
| `SERIOUS` | A serious message was detected, so jokes are suppressed |
| `WINDING_DOWN` | The conversation looks like it's fading |
| `CONFUSED` | It was unsure, so it re-read more history |
| `DM_CHECKIN_SCAN`, `DM_CHECKIN` | Check-in eligibility and sends |

All errors are logged with a full traceback.

---

## Troubleshooting

**The bot is online but never replies**
Check that Message Content Intent is enabled in the Developer Portal. Look for `RECV` lines in the logs: if they show empty content, the intent is the problem. Also remember the reply delay is 15 to 300 seconds by default. Lower `rd_min` and `rd_max` while testing.

**`TypeError` about missing `intents` on startup**
Recent versions of discord.py require intents to be passed to `discord.Client(...)`. Pass an intents object with `message_content` (and `members` if you use it) enabled.

**Images are never sent**
Look at the startup warnings. `img_send_on` is switched off automatically if `requests` isn't installed or `browserless_token` is empty. If it's enabled but nothing is sent, search the logs for `browserless` messages: a 401 means a bad token and a 429 means you hit your rate limit.

**`model_decommissioned` errors**
Groq retired the model. Update `model` and `vmodel` (see the admin guide).

**Replies are cut off or empty**
Reasoning models can spend part of the token budget on hidden thinking. The bot already requests no reasoning where supported, and `max_tokens` is set high. If you switch to a new reasoning model, add it to `REASONING_MODELS`.

**Check-ins never happen**
Set `log_level = "DEBUG"` and look for `DM_CHECKIN_SCAN` lines. Each known user is logged with the reason they were skipped: no DM history, silence gap too short, or not enough messages.

---

## Notes and limits

- **Image scraping is fragile.** It relies on rendering Pinterest search pages through Browserless. If Pinterest changes its pages or blocks the requests, image sends will fail quietly and the bot falls back to a normal text reply.
- **Message storage.** The bot stores recent chat lines and per-person facts on disk in plain JSON. Tell the people in your server that it remembers things, and delete the files if anyone asks.
- **Cost.** Every reply is at least one Groq call, plus smaller calls for image detection, summaries and topic guessing. The free tier is usually enough for a small server.
- **Discord rules.** Run it as a proper bot account in servers where it is welcome, and follow Discord's Terms of Service and Developer Policy.

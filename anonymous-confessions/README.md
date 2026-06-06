# 🕵️ Anonymous Confessions — Discord Bot

A production-ready Discord bot that lets server members submit confessions, secrets, and stories **anonymously**, with discussion threads, advice, reactions, reports, and full moderation tooling.

> **MVP scope.** This build covers the core: `/confess`, anonymous posting, advice modals, reaction tracking, auto-threads, moderation (`/approve`, `/reject`, `/banconfess`, etc.), reports, per-guild settings, and stats. The feature spec also describes Guess-Who, leaderboards, daily featured confession, and an anonymous chat relay — those are intentionally out of scope for this iteration but the database schema and cog structure leave room to add them.

---

## ✨ Features

- **`/confess`** opens a Discord modal; the bot posts the confession anonymously with a category badge, baseline reactions, and a discussion thread.
- **Advice button (💡)** under every confession opens a modal; advice is posted anonymously in the thread.
- **Report button (🚩)** sends a report to the mod channel.
- **Categorisation** via offline keyword matching (Relationships, School, Work, Family, Embarrassing, Funny, Emotional, generic Confession).
- **Anti-abuse**: per-user cooldown, duplicate detection (hash-based), profanity filter, hard-block list for self-harm encouragement / doxxing patterns.
- **Moderation**: optional approval queue, `/approve`, `/reject`, `/deleteconfession`, `/banconfess`, `/unbanconfess`, audited `/whoposted` for full admins only.
- **Persistent buttons** — Advice / Report keep working after the bot restarts.
- **MongoDB** storage via Motor (async).
- **Per-guild settings** for confession channel and mod channel.

---

## 📁 Project layout

```
anonymous-confessions/
├── bot/
│   ├── bot.py              # Bot class + entrypoint
│   ├── config.py           # Env-var driven config
│   ├── cogs/
│   │   ├── confessions.py  # /confess, posting, reactions, DM listener
│   │   ├── moderation.py   # /approve /reject /banconfess /whoposted …
│   │   ├── settings.py     # /setchannel /setmodchannel /settings
│   │   ├── stats.py        # /stats /help
│   │   └── views.py        # Persistent buttons + modals
│   ├── db/mongo.py         # Async MongoDB layer
│   └── utils/              # embeds, categories, security, logging
├── main.py
├── requirements.txt
├── .env.example
├── Dockerfile
├── Procfile
└── README.md
```

---

## 🚀 Quick start (local)

### 1. Create the Discord application

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Add Bot** → copy the **Token** (you'll paste it in `.env`).
3. Under **Privileged Gateway Intents**, enable **Message Content Intent** (used by the DM listener).
4. **OAuth2 → URL Generator**: select scopes `bot` and `applications.commands`.
   Required bot permissions: `View Channels`, `Send Messages`, `Embed Links`, `Add Reactions`, `Read Message History`, `Create Public Threads`, `Send Messages in Threads`, `Manage Messages` (used by `/deleteconfession`).
5. Open the generated URL and invite the bot to your server.

### 2. Run MongoDB

Anything Mongo-compatible works. Local dev:

```bash
docker run -d --name mongo -p 27017:27017 mongo:7
```

Or use **MongoDB Atlas** and copy the connection string.

### 3. Install + run

```bash
git clone <this-repo>
cd anonymous-confessions
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: DISCORD_TOKEN, MONGO_URI, (optional) DEV_GUILD_ID
python main.py
```

On first start the bot will sync slash commands. If `DEV_GUILD_ID` is set, commands appear in that server instantly; otherwise global sync can take ~1 hour to propagate.

### 4. Configure the server

In Discord:

```
/setchannel #confessions       (required)
/setmodchannel #mod-log        (optional, for reports & approval queue)
/help
```

Now anyone can run `/confess`.

---

## ⚙️ Configuration

All settings live in `.env` (see `.env.example`):

| Var | Default | Purpose |
|---|---|---|
| `DISCORD_TOKEN` | — | Required. Bot token. |
| `DEV_GUILD_ID` | — | Optional. Sync slash commands to a single guild for fast iteration. |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string. |
| `MONGO_DB` | `anon_confessions` | Database name. |
| `CONFESSION_COOLDOWN_SECONDS` | `600` | Per-user cooldown between submissions. |
| `REQUIRE_APPROVAL` | `false` | If `true`, confessions go to the mod channel and need `/approve`. |
| `LOG_LEVEL` | `INFO` | Standard Python log level. |

---

## 🗄️ Data model

MongoDB collections:

- **users** — `user_id`, `confession_count`, `advice_count`, `banned`, `last_confession_ts`, `created_at`
- **confessions** — `confession_id`, `guild_id`, `author_id` *(private)*, `content`, `content_hash`, `category`, `status`, `message_id`, `thread_id`, `channel_id`, `reactions`, `created_at`
- **advice** — `advice_id`, `confession_id`, `advisor_id` *(private)*, `content`, `created_at`
- **reports** — `confession_id`, `reporter_id`, `reason`, `created_at`
- **guilds** — `guild_id`, `confession_channel_id`, `mod_channel_id`
- **counters** — internal monotonic sequence for confession/advice IDs

`author_id` and `advisor_id` are **never** sent to non-admin members. The only command that exposes an author is `/whoposted`, which is gated on the `Administrator` permission and writes a `WARNING`-level audit log line.

---

## 🛡️ Security notes

- Slash commands that touch identity data require `Administrator` (or `Manage Guild` for ban/approve flows).
- All confession-author replies to the user are **ephemeral** so onlookers can't link the author to the post.
- Cooldowns are enforced server-side, not just by Discord's rate limits.
- Duplicate detection hashes a normalised version of the text (lowercased, whitespace collapsed).
- Profanity is filtered with [`better-profanity`](https://pypi.org/project/better-profanity/); a small hard-block list rejects messages with self-harm encouragement or "phone number is …" / "home address" patterns.
- Store `.env` outside version control. The bot will refuse to start without `DISCORD_TOKEN`.

---

## 🐳 Docker

```bash
docker build -t anon-confessions .
docker run --env-file .env --restart unless-stopped anon-confessions
```

---

## ☁️ Deploying

The bot is a long-running worker (no inbound HTTP). Any host that can keep a Python process alive will work. Two common options:

### Railway

1. Push this repo to GitHub.
2. **New Project → Deploy from GitHub repo**, pick this repo.
3. Add a **Mongo** plugin (or use Atlas) and copy its connection string.
4. **Variables** tab: set `DISCORD_TOKEN`, `MONGO_URI`, `MONGO_DB`, and any optional vars.
5. Railway auto-detects the `Procfile` and runs `python main.py`. Done.

### Render

1. **New → Background Worker**, point at this repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `python main.py`
4. Add env vars in the dashboard (same as above). Use Render's MongoDB add-on or Atlas.

### Fly.io / VPS / Docker host

Use the included `Dockerfile`. Just provide the env vars at runtime.

---

## 🧭 Extending

Hooks for the features that aren't in this MVP:

- **Guess Who** — add a `guesses` collection (already in the spec'd schema) and a third button on `ConfessionView` that opens a modal collecting a `discord.Member`. Aggregate counts in a `/topguessed` command.
- **Leaderboards** — query `users` sorted by `confession_count` / `advice_count` and `confessions` aggregated by `reactions` totals.
- **Daily Featured Confession** — start a `discord.ext.tasks.loop(hours=24)` in a new cog; pick the past day's confession with the highest reaction total.
- **Anonymous chat relay** — store a `sessions` collection with two `user_id`s, listen for DMs, look up the active session, forward via `bot.get_user(other).send(...)`.

The cog system and the `Database` class are designed so each of those is additive.

---

## 📜 License

MIT — do what you want, just don't dox your users.

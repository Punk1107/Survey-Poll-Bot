<div align="center">
  <img src="assets/banner.png" alt="Survey Poll & Analytics Bot Banner" width="100%">
  <br />
  <img src="assets/logo.png" alt="Survey Poll & Analytics Bot Logo" width="128">
  <h1>Discord Server Analytics & Survey Poll Bot</h1>
  <p>A modular monolith Discord bot built with <b>Python + discord.py + SQLite + Web Server + Scheduler</b> for server activity analytics, scheduled reports, and interactive surveys.</p>

  [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
  [![discord.py](https://img.shields.io/badge/discord.py-2.3.2%2B-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
  [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00)](https://docs.sqlalchemy.org/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Deploy on Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)](https://render.com)
  [![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
</div>

---

## 🚀 Overview

**Discord Server Analytics & Survey Bot** is a high-performance, modular monolith Discord bot. It provides:
1. **Server Activity Analytics (V1.1)** — Real-time tracking of server messages, active users, top channels, peak active hours, member join/leave trends, and automated daily/weekly scheduled reports per guild timezone.
2. **Interactive Survey & Poll System** — Guided multi-step feedback collection with Multiple Choice (MCQ), Star Ratings (1–5), Free-Text responses, anonymous privacy protection, visual bar charts, and CSV/JSON exports.
3. **Web Server & Health Check** — Built-in `aiohttp` web server for keep-alive monitoring on 24/7 hosting platforms like [Render](https://render.com) and UptimeRobot.

---

## ✨ Features

| Category | Details |
| :--- | :--- |
| 📊 **Server Analytics** | Messages count, active users, top channels, peak hours (0–23h), and member growth |
| 📅 **Scheduled Reports** | Per-guild configurable report time & timezone with automated Daily and Weekly reports |
| 🏆 **Leaderboards** | Top active server contributors for Today or the Last 7 Days |
| ⚙️ **Guild Configuration** | Slash-command group (`/config`) for stats channel, daily/weekly toggles, report time, and timezone |
| 🔘 **Multi-Type Surveys** | Multiple Choice (MCQ), Star Ratings (1–5), Free-Text answers |
| 🔒 **Privacy Protection** | Anonymous survey mode masks all respondent identities with SHA-256 tokens |
| 📥 **Flexible Export** | CSV (Excel-ready `utf-8-sig`) and JSON export |
| 🌐 **Keep-Alive Web Server** | `aiohttp` server exposing status dashboard (`/`), health metrics (`/health`), and UptimeRobot probe (`/ping`) |
| ⚡ **Modular Monolith** | Clear separation between Database Repositories, Discord Client/Events/Commands, Business Logic Services, Reports, and Web |
| 🧪 **Tested Architecture** | Full test suite using `pytest` and `pytest-asyncio` |

---

## 🛠️ Quick Start

### Prerequisites
- **Python 3.10+**
- A Discord Bot Token from the [Discord Developer Portal](https://discord.com/developers/applications)
- Bot requires **`applications.commands`** scope and **`bot`** scope with **Message Content** & **Server Members** Intent enabled.

### 1. Clone & Install

```bash
git clone https://github.com/Punk1107/Survey-Poll-Bot.git
cd Survey-Poll-Bot

python -m venv venv
# macOS / Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root (see `.env.example`):

```env
# Required
DISCORD_TOKEN=your_discord_bot_token_here

# Database
DATABASE_URL=sqlite:///surveys.db
DB_PATH=data/analytics.db

# Settings
PORT=8080
DEFAULT_TIMEZONE=Asia/Bangkok
LOG_LEVEL=INFO
```

### 3. Run

```bash
python bot.py
```

Slash commands will automatically sync with Discord on startup.

---

## ⚙️ Environment Variables Reference

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `DISCORD_TOKEN` | ✅ | — | Discord bot token |
| `DATABASE_URL` | ❌ | `sqlite:///surveys.db` | Survey SQLAlchemy database URL |
| `DB_PATH` | ❌ | `data/analytics.db` | Server analytics SQLite path |
| `DEFAULT_TIMEZONE` | ❌ | `Asia/Bangkok` | Default IANA timezone for guilds |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `PORT` | ❌ | `8080` | Web server port (Render sets this automatically) |
| `HOST` | ❌ | `0.0.0.0` | Web server bind address |

---

## 🎮 Command Reference

### 📊 Server Analytics Commands

| Command | Description |
| :--- | :--- |
| `/stats [period]` | View server activity stats (`Today` or `Last 7 days`) |
| `/userstats [user] [period]` | View member activity statistics (defaults to self) |
| `/leaderboard [period]` | Show top active contributors with medal rankings |

### ⚙️ Analytics Admin Configuration (`/config`)

| Command | Description |
| :--- | :--- |
| `/config stats-channel <#channel>` | Set channel where scheduled reports will be sent |
| `/config daily <on\|off>` | Enable or disable daily analytics reports |
| `/config weekly <on\|off>` | Enable or disable weekly analytics reports (Mondays) |
| `/config report-time <HH:MM>` | Set scheduled report delivery time (24-hour clock) |
| `/config timezone <IANA>` | Set guild timezone (e.g. `Asia/Bangkok`, `UTC`, `America/New_York`) |
| `/config status` | Show current guild analytics configuration |

### 📋 Survey & Poll Commands (`/survey`)

| Command | Description |
| :--- | :--- |
| `/survey create` | Create a new survey |
| `/survey add-question` | Add a question (MCQ / Rating / Text) |
| `/survey add-choice` | Add choice option to MCQ question |
| `/survey preview` | Preview survey before publishing |
| `/survey publish` | Publish survey for members to answer |
| `/survey answer` | Join & answer a published survey |
| `/survey close` | Close a survey |
| `/survey list` | List surveys you created |
| `/survey results` | View live visual analytics (bar charts / ratings) |
| `/survey export` | Download survey responses as CSV or JSON |
| `/survey delete` | Delete a survey |

---

## 🏛️ V1.1 Architecture (Modular Monolith)

The project separates Database Data Access, Discord API / Events / Commands, Business Logic Services, Report Builders, Utilities, and Web Server:

```text
discord-analytics-bot/
│
├── bot.py                     # Entry point (registers events/commands, starts scheduler & web)
├── config.py                  # Environment configuration & startup validation
├── requirements.txt           # Dependencies
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
├── pytest.ini                 # Pytest configuration
├── README.md                  # Documentation
│
├── data/                      # Database storage directory
│   └── analytics.db
│
├── database/                  # Database Layer
│   ├── connection.py          # SQLite connection, WAL mode, StaticPool, PRAGMAs
│   ├── migrations.py          # Schema versioning (user_version PRAGMA)
│   ├── survey_helpers.py      # Survey domain queries
│   └── repositories/          # Data Access Layer (Repository Pattern)
│       ├── guild_repository.py     # analytics_guilds & guild_settings CRUD
│       ├── user_repository.py      # analytics_users & daily_user_stats CRUD
│       ├── channel_repository.py   # analytics_channels & daily_channel_stats CRUD
│       ├── activity_repository.py  # Atomic multi-table UPSERTs for message activity
│       └── report_repository.py    # Report delivery dedup tracking
│
├── bot/                       # Discord Layer
│   ├── client.py              # Bot factory with required Intents
│   ├── events/                # Event Handlers
│   │   ├── message_events.py  # on_message (activity tracking)
│   │   ├── member_events.py   # on_member_join / on_member_remove
│   │   └── guild_events.py    # on_guild_join / on_guild_remove & slash command sync
│   └── commands/              # Slash Commands
│       ├── stats.py           # /stats
│       ├── userstats.py       # /userstats
│       ├── leaderboard.py     # /leaderboard
│       └── config.py          # /config group
│
├── services/                  # Business Logic Layer
│   ├── activity_service.py    # Event processing & timezone resolution
│   ├── analytics_service.py   # Aggregation & summary calculations
│   ├── report_service.py      # Assembles & delivers reports
│   └── scheduler_service.py   # 1-minute background loop for scheduled reports
│
├── reports/                   # Presentation & Embeds Layer
│   ├── daily_report.py        # DailyReport data model
│   ├── weekly_report.py       # WeeklyReport data model
│   ├── embeds.py              # Discord Embed builders
│   └── formatters.py          # Bar charts, numbers, percentages, peak hours
│
├── web/                       # Web Server Layer
│   ├── webserver.py           # WebServer lifecycle (start/stop)
│   ├── routes.py              # GET /, GET /health, GET /ping, /api/* stubs
│   └── health.py              # Health check JSON payload builder
│
├── utils/                     # Utilities
│   ├── logger.py              # Centralised logging setup
│   ├── permissions.py         # Administrator / Manage Guild check
│   ├── time.py                # Timezone & date-range helpers
│   ├── validators.py          # Slash-command input validators
│   └── survey_ui.py           # Survey question UI renderer
│
└── tests/                     # Automated Test Suite
    ├── test_database.py       # Repository & Migration tests
    ├── test_analytics.py      # Analytics queries & Leaderboard tests
    ├── test_reports.py        # Report models & Embed builder tests
    └── test_utils.py          # Time, Timezone, and Validator tests
```

---

## 🧪 Testing

Run the automated test suite with `pytest`:

```bash
python -m pytest tests/
```

All 28 tests cover Database Repositories, Migrations, Analytics Queries, Leaderboards, Report Builders, Timezone Logic, and Input Validators.

---

## 🌐 Web Server & Deployment

The bot includes an `aiohttp` web server for keep-alive probes when deployed on platforms like **Render.com**.

### Web Endpoints

| Endpoint | Description |
| :--- | :--- |
| `GET /` | Rich HTML status dashboard (auto-refreshes every 30s) |
| `GET /health` | JSON health metrics (`status`, `latency_ms`, `guilds`, `uptime_s`) |
| `GET /ping` | Plain-text `pong` probe for UptimeRobot |

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

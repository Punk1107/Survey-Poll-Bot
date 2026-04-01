<div align="center">
  <img src="assets/banner.png" alt="Survey Poll Bot Banner" width="100%">
  <br />
  <img src="assets/logo.png" alt="Survey Poll Bot Logo" width="128">
  <h1>Survey Poll Bot</h1>
  <p>A professional, feature-rich Discord bot for creating surveys, collecting responses, and analyzing results — all through slash commands.</p>

  [![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
  [![discord.py](https://img.shields.io/badge/discord.py-2.3.2%2B-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
  [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00)](https://docs.sqlalchemy.org/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Deploy on Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)](https://render.com)
  [![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
</div>

---

## 🚀 Overview

**Survey Poll Bot** is a comprehensive Discord slash-command bot built for communities, organizations, and researchers who need structured, scalable feedback collection. It features a guided multi-step survey experience, three question types, real-time analytics with visual bar charts, privacy-aware data export, and a built-in health-check web server for 24/7 uptime on platforms like [Render](https://render.com).

---

## ✨ Features

| Category | Details |
| :--- | :--- |
| 🔘 **Multi-Type Questions** | Multiple Choice (MCQ), Star Ratings (1–5), Free-Text answers |
| 🔒 **Privacy Modes** | Anonymous mode masks all respondent identities (even in exports) |
| 📈 **Visual Analytics** | ASCII bar charts with percentages & vote counts for MCQ; avg/min/max for ratings |
| 📥 **Flexible Export** | CSV (Excel-ready with utf-8-sig encoding) and JSON (API-friendly) |
| 🎮 **Guided UX** | Interactive button/select/modal flow — participants are guided question-by-question |
| 🔄 **Lifecycle Management** | Create → Preview → Publish → Close → Reopen → Delete with confirmation dialogs |
| 🌐 **Keep-Alive Web Server** | Built-in `aiohttp` server exposes `/ping`, `/health` (JSON), and `/` (status dashboard) |
| ⚡ **High-Performance DB** | SQLAlchemy 2.0 async engine, WAL mode, 128 MB mmap, busy-timeout, StaticPool |
| 🔁 **Auto Schema Migrations** | Missing columns are added automatically on startup — no manual `ALTER TABLE` needed |
| 🛡️ **Robust Error Handling** | Granular slash-command error handler for permissions, cooldowns, and internal errors |

---

## 🛠️ Quick Start

### Prerequisites
- **Python 3.10+**
- A Discord Bot Token — create one at the [Discord Developer Portal](https://discord.com/developers/applications)
- Bot must have the **`applications.commands`** scope and **`bot`** scope when invited

### 1. Clone & install

```bash
git clone https://github.com/Punk1107/Survey-Poll-Bot.git
cd Survey-Poll-Bot

python -m venv venv
# macOS / Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirement.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
# Required
DISCORD_TOKEN=your_bot_token_here

# Optional — defaults shown below
DATABASE_URL=sqlite:///surveys.db
LOG_LEVEL=INFO
```

> **Tip:** For production, swap `DATABASE_URL` for a PostgreSQL URL (`postgresql+asyncpg://...`) and the bot will use a connection pool automatically.

### 3. Run

```bash
python bot.py
```

Slash commands are synced automatically on the first `on_ready` event.

---

## ⚙️ Configuration Reference

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `DISCORD_TOKEN` | ✅ | — | Your Discord bot token |
| `DATABASE_URL` | ❌ | `sqlite:///surveys.db` | SQLAlchemy-compatible DB URL |
| `LOG_LEVEL` | ❌ | `INFO` | `DEBUG` · `INFO` · `WARNING` · `ERROR` |
| `PORT` | ❌ | `8080` | Web server port (auto-set by Render) |
| `HOST` | ❌ | `0.0.0.0` | Web server bind address |

---

## 🎮 Command Reference

All interactions use Discord **Slash Commands** under the `/survey` group.

### 🛠️ Setup

| Command | Description |
| :--- | :--- |
| `/survey create` | Create a new survey (title, anonymous toggle, optional description) |
| `/survey add-question` | Add a question — choose type: MCQ / Rating / Text |
| `/survey add-choice` | Add an answer option to an MCQ question (up to 25) |

### 🚀 Publishing

| Command | Description |
| :--- | :--- |
| `/survey preview` | Preview your survey before going live (ephemeral) |
| `/survey publish` | Open the survey so members can answer |
| `/survey close` | Stop accepting new responses |
| `/survey reopen` | Reopen a previously closed survey |

### 📝 Participation

| Command | Description |
| :--- | :--- |
| `/survey answer` | Join a published survey — the bot guides you through each question |

### 📊 Management & Results

| Command | Description |
| :--- | :--- |
| `/survey list` | See all surveys you have created (status badges included) |
| `/survey info` | Full metadata: status, question count, response count, creator |
| `/survey results` | Visual analytics — bar charts, star ratings, text snippets |
| `/survey export` | Download results as **CSV** or **JSON** |
| `/survey delete` | ⚠️ Permanently delete a survey (requires confirmation) |

### ❓ Help

| Command | Description |
| :--- | :--- |
| `/survey help` | Show this command reference inside Discord |

### ⚡ Typical Workflow

```
1. /survey create          → give your survey a title
2. /survey add-question    → add questions (repeat for each)
3. /survey add-choice      → add options to MCQ questions
4. /survey preview         → double-check everything
5. /survey publish         → let people answer!
6. /survey results         → view live analytics
7. /survey export          → download the raw data
```

---

## 📈 Analytics & Export

### MCQ Stats (bar chart with %)
```
██████████  100%  Option A
████░░░░░░   40%  Option B
██░░░░░░░░   20%  Option C

📊 Total votes: 10
```

### Rating Stats
```
⭐⭐⭐⭐ 4.2 / 5
Responses: 24 | Min: 2 | Max: 5
```

### Export Formats
- **CSV** — `utf-8-sig` encoding for seamless Excel compatibility
- **JSON** — `records` orientation, UTF-8, pretty-printed
- **Privacy** — Anonymous surveys automatically mask `user_id` with a SHA-256 token at export time

---

## 🌐 Deployment on Render

The repo includes a `render.yaml` for one-click deploy to [Render.com](https://render.com).

1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com) → **New → Web Service**
3. Connect your GitHub repo — Render auto-detects `render.yaml`
4. Set **`DISCORD_TOKEN`** in the Environment Variables tab
5. Deploy — Render polls `/health` to verify the service is up

**Keep-alive with UptimeRobot:**  
Add a monitor pointing to `https://<your-app>.onrender.com/ping` with keyword `pong` — this prevents the free tier from sleeping.

### Available Endpoints

| Endpoint | Description |
| :--- | :--- |
| `GET /` | HTML status dashboard (auto-refreshes every 30s) |
| `GET /health` | JSON health payload — HTTP 200 when ready, 503 when starting |
| `GET /ping` | Plain-text `pong` — simplest UptimeRobot probe |

---

## 📂 Project Structure

```
Survey-Poll-Bot/
├── assets/            # Visual assets (logo, banner)
├── views/
│   ├── mcq.py         # MCQView + MCQSelect — choice dropdown UI
│   ├── rating.py      # RatingView + RatingButton — star rating UI
│   └── text.py        # TextModal + TextPromptView — free-text UI
├── analytics.py       # Statistics queries & formatted field builders
├── bot.py             # Entry point — slash command definitions & lifecycle
├── config.py          # Environment variable loading & validation
├── database.py        # Async SQLAlchemy engine, session factory, domain helpers
├── export.py          # CSV / JSON export with anonymous masking
├── models.py          # ORM models: Survey, Question, Choice, Response, Answer
├── utils.py           # Shared UI helpers (send_question_ui, _send dispatcher)
├── webserver.py       # aiohttp keep-alive server (/, /health, /ping)
├── render.yaml        # Render.com deployment config
├── requirement.txt    # Python dependencies
└── .env               # Local secrets (not committed)
```

---

## 🗄️ Database Schema

```
Survey ──< Question ──< Choice
  └──────< Response ──< Answer
```

| Table | Key Columns |
| :--- | :--- |
| `surveys` | `id`, `title`, `description`, `creator_id`, `is_anonymous`, `is_published`, `is_closed` |
| `questions` | `id`, `survey_id`, `text`, `qtype` (`mcq`/`rating`/`text`), `order` |
| `choices` | `id`, `question_id`, `text` |
| `responses` | `id`, `survey_id`, `user_id`, `submitted_at` (unique per user/survey) |
| `answers` | `id`, `response_id`, `question_id`, `answer` |

Schema migrations run automatically on startup — new columns are added without manual intervention.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

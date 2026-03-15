<div align="center">
  <img src="assets/banner.png" alt="Survey Poll Bot Banner" width="100%">
  <br />
  <img src="assets/logo.png" alt="Survey Poll Bot Logo" width="128">
  <h1>Survey Poll Bot</h1>
  <p>A professional, highly-customizable Discord survey and polling system.</p>

  [![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
  [![Discord.py](https://img.shields.io/badge/discord.py-2.3.2%2B-5865F2.svg)](https://discordpy.readthedocs.io/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
</div>

---

## 🚀 Overview

**Survey Poll Bot** is a comprehensive Discord slash-command bot designed for organizations, communities, and researchers who need structured feedback. It supports multi-step surveys with various question types, real-time analytics, and data export.

## ✨ Key Features

- 🛠️ **Multi-Type Questions**: Support for Multiple Choice (MCQ), Star Ratings (1-5), and Open-ended Text responses.
- 🔒 **Privacy Modes**: Toggle between Anonymous and Public response modes for each survey.
- 📈 **Real-time Analytics**: Built-in visual statistics for MCQ and rating questions.
- 📥 **Flexible Export**: Download survey results in CSV (Excel-ready) or JSON formats.
- ⚡ **Optimized Performance**: Built with SQLAlchemy 2.0 and high-performance database interactions.
- 🔄 **Sequential UI**: Interactive, button-driven survey experience for participants.

---

## 🛠️ Quick Start

### Prerequisites
- **Python 3.10+**
- A Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Punk1107/Survey-Poll-Bot.git
   cd Survey-Poll-Bot
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirement.txt
   ```

---

## ⚙️ Configuration

Create a `.env` file in the root directory and add your bot token:

```env
DISCORD_TOKEN=your_token_here
DATABASE_URL=sqlite:///surveys.db
LOG_LEVEL=INFO
```

---

## 🎮 Command Usage

All bot interactions use Discord **Slash Commands**.

| Command | Description |
| :--- | :--- |
| `/survey create` | Start a new survey draft. |
| `/survey add-question` | Add MCQ, Rating, or Text questions to a draft. |
| `/survey add-choice` | Add options to an MCQ question. |
| `/survey preview` | View your survey as respondents will see it. |
| `/survey publish` | Go live and allow members to answer. |
| `/survey answer` | Enter a published survey to participate. |
| `/survey list` | View all surveys you have created. |
| `/survey info` | Detailed metadata about a specific survey. |
| `/survey results` | View the current statistics and text answers. |
| `/survey export` | Download results as CSV or JSON. |
| `/survey close` | Stop accepting new responses. |
| `/survey delete` | Permanently remove a survey and its data. |

---

## 📊 Analytics & Export

The bot provides instant visual feedback for survey creators.

- **MCQ Stats**: Percentage breakdown of choices with horizontal bar visual.
- **Rating Stats**: Average stars and distribution counts.
- **Text Answers**: Snippets of the most recent open-ended responses.
- **Bulk Export**: Get the raw data anytime for external analysis in Excel, Pandas, or other tools.

---

## 📂 Project Structure

```text
├── assets/            # Visual assets (Logo, Banner)
├── views/             # Custom Discord UI Views & Modals
├── analytics.py       # Statistics generation logic
├── bot.py             # Main entry point & Command definitions
├── database.py        # SQLAlchemy engine & complex queries
├── export.py          # CSV/JSON generation logic
├── models.py          # Database schema (SQLAlchemy)
└── utils.py           # UI helpers and shared utilities
```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

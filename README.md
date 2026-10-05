# 🤖 Focus Reminder Bot

A Telegram bot with **three separate, independent systems** for managing your productivity:

- **💤 AFK System** - Mark yourself as unavailable
- **⏰ Reminder System** - Schedule reminders for tasks
- **📚 Focus Mode** - Self-discipline study sessions with fun callouts

---

## 🚀 Features

### 💤 AFK System
- Set an AFK status with optional reason
- Automatically removed when you send a message (coming soon)
- Notifies others when they mention you: *"@Alex is currently AFK - Reason: sleeping"* (coming soon)

### ⏰ Reminder System
- Create reminders with flexible time formats (2h, 30m, etc.)
- Reminders sent to private chat by default
- Support for recurring reminders (daily, weekly, monthly - coming soon)
- Edit, pause, or delete reminders (coming soon)
- Multiple reminder personalities (gentle, funny, strict - coming soon)

### 📚 Focus Mode
- Commit to focused study/work sessions
- Choose intensity level: 😌 Gentle, 😤 Strict, 💀 Brutal
- Bot gently calls you out when you chat during focus (coming soon)
- Smart warning system with cooldowns (prevents spam - coming soon)
- Private, group, or silent mode options
- Track your focus statistics and streaks (coming soon)

---

## 📋 Requirements

- Python 3.9+
- Telegram Bot Token (get one from [@BotFather](https://t.me/botfather))
- SQLite (included with Python)

---

## 🔧 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/itseloxo/telegram-focus-reminder-bot.git
   cd telegram-focus-reminder-bot
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create `.env` file:**
   ```bash
   cp .env.example .env
   ```

5. **Edit `.env` with your settings:**
   ```
   BOT_TOKEN=your_token_here
   BOT_ADMIN_ID=your_user_id_here
   ```

6. **Run the bot:**
   ```bash
   python main.py
   ```

---

## 📖 Commands

### AFK
- `/afk [reason]` - Mark as AFK
- `/unafk` - Remove AFK status

### Reminders
- `/remind [time] [task]` - Create reminder
- `/reminders` - List all reminders
- `/timezone [tz]` - Set timezone (UTC, US/Eastern, etc.)

### Focus Mode
- `/focus [duration] [goal]` - Start focus session
- `/focusoff` - End focus session
- `/focusstats` - View focus statistics

### General
- `/start` - Start the bot
- `/help` - Show all commands

---

## 🏗️ Architecture

Each system is **completely independent**:

```
Database Models:
├── AFK (unavailability status)
├── Reminder (scheduled tasks)
├── FocusSession (self-discipline sessions)
└── User (shared user settings)

Handlers:
├── bot/handlers/afk.py (AFK system)
├── bot/handlers/reminder.py (Reminder system)
├── bot/handlers/focus.py (Focus system)
└── bot/handlers/common.py (General commands)

Background Jobs:
└── APScheduler (persistent job store for reminders & focus timers)
```

---

## ⚙️ Configuration

Edit `.env` to customize:

```
FOCUS_WARNING_COOLDOWN_MINUTES=10      # Time between focus warnings
FOCUS_MAX_WARNINGS_PER_SESSION=3       # Max public warnings per session
FOCUS_PAUSE_MAX_DURATION_MINUTES=120   # Maximum pause duration
DEFAULT_TIMEZONE=UTC                   # Default user timezone
```

---

## 🔐 Privacy

- **AFK**: Public (group visibility only when mentioned)
- **Reminders**: Private by default (sent to bot DM)
- **Focus Mode**: User-configurable (private/group/silent)

---

## 🐛 Troubleshooting

**Bot doesn't respond:**
- Check BOT_TOKEN in `.env`
- Ensure bot has required permissions in the group

**Reminders not firing:**
- Check database file exists (bot.db)
- Restart the bot to rebuild scheduler state
- Check logs for errors

**Focus warnings too frequent:**
- Adjust `FOCUS_WARNING_COOLDOWN_MINUTES` in `.env`
- Or reduce `FOCUS_MAX_WARNINGS_PER_SESSION`

---

## 📝 License

MIT License - see LICENSE file for details

---

## 🤝 Contributing

Contributions welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

---

## 📧 Support

If you need help:
1. Check existing GitHub issues
2. Create a new issue with detailed description
3. Include logs and reproduction steps

---

**Made with ❤️ for productive people**

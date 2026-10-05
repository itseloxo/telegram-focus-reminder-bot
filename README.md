# 🤝 FamigoBot

A Telegram group bot for building voluntary, group-specific social connections, with separate AFK, reminder, and focus tools.

---

## 🚀 Features

### 🤝 Famigo social features
- Create an optional profile separately in each group
- Add group-specific interests and discover members with shared interests
- Send a connection request that only its recipient can accept or decline
- Hide your profile, export group profile data privately, or delete your group profile
- Open a Telegram Mini App to browse, search, and edit profiles in the current group
- Launch the group directory from Telegram inline mode, then browse profiles and request connections in the Mini App

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

- Python 3.12+
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
   BOT_ADMIN_ID=123456789
   ```
   Set `BOT_ADMIN_ID` to your numeric Telegram user ID; do not leave it as text or a placeholder.

6. **Run the bot:**
   ```bash
   python main.py
   ```
   The bot publishes its available commands to Telegram when it starts. Open the bot chat and type `/` to see them.

---

## 📖 Commands

### Famigo (use in a group)
- `/famigo` - Show available Famigo commands
- `/famigo` also opens buttons for the group directory in inline mode and the Mini App
- `/profile` - View your profile in this group
- `/setprofile field | value` - Set an optional field (for example, `/setprofile bio | I enjoy hiking`)
- `/interests`, `/addinterest [interest]`, and `/removeinterest [interest]` - Manage group-specific interests
- `/currently category | activity` - Share something you chose to do; `/watching`, `/listening`, `/reading`, and `/playing` are shortcuts
- `/addfavorite category | item`, `/favorites`, and `/removefavorite category | item` - Manage group-specific favorites
- `/mood [mood]` - Set a voluntary mood that expires after 24 hours; `/mood off` clears it
- `/discover` - Find a group member with shared interests; `/random` picks a member fairly and avoids your last pick
- `/connect @username [relationship]` - Send a confirmation-based connection request; reply to a member's message if they do not have a username
- `/relationships` - List your approved connections
- `/stats` - View group-specific profile stats
- `/addsocial [platform] [username-or-https-url]`, `/socials`, and `/deletesocial [platform]` - Manage private user-level social links
- `/privacy` and `/setprofileprivacy public|group_only|hidden` - Manage this group's profile visibility
- `/discoverability on|off` and `/connectionrequests on|off` - Set global opt-outs that apply in every group
- `/export` - Privately send your Famigo data from this group
- `/deleteprofile` - Confirm and delete your Famigo data from this group
- `/mygroups` - Privately list your group-specific profiles

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

Famigo profile, interest, discovery, and connection operations are group-scoped and separated into handlers and services:

```
bot/handlers/famigo.py
bot/services/famigo.py
database.py
```

Profile export and group-list output are sent privately. The bot can only deliver them if the user has started a private chat with it. Every Mini App API request verifies Telegram's signed `initData` and confirms that the user is currently a member of the requested group; profile and activity queries always include that group's ID. Telegram inline queries do not reveal the destination chat ID, so Famigo's inline result is a safe launcher rather than a profile card; profile details are only shown after opening the Mini App and verifying group membership. Group commands such as `/profile` and `/discover` display results in the group itself.

### Telegram Mini App and inline setup

1. Deploy the bot on Railway and generate a public HTTPS domain for its service.
2. Set `WEBAPP_URL` in Railway to that domain's root URL (for example, `https://your-service.up.railway.app`). Railway provides `PORT`; the bot serves the Mini App and API on that port.
3. In a private chat with `@BotFather`, run `/setdomain` and select this bot, then enter the Railway domain **without** `https://` or a path.
4. In BotFather, run `/setinline` for this bot and set a short placeholder such as `Find a group member`. Restart/redeploy the bot after changing variables.
5. Add the bot to a group and make it an administrator so Telegram can reliably verify members. Run `/famigo` in that group; members can use **Open Mini App** or **Find members inline**.

The bot's persistent menu also opens the Mini App. If opened without a group context, users can choose from groups where they already have a Famigo profile. New users should open the Mini App from `/famigo` in the group first. Profiles start visible to group members and can be hidden by their owner. No profile is made globally browsable. The app is a first social release; confessions, birthdays and member history, community insights, reputation/achievement criteria, the full relationship graph, database migrations, and several advanced reminder/focus workflows remain unfinished.

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
- Start a private chat with the bot using `/start` so it can message you.
- Check the Railway logs for delivery errors.
- Active reminders are restored from the database when the bot restarts.

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

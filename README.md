
---

# What Chats Do I Own

A Telegram bot built using **Telethon** that helps users view a list of groups and channels they own or manage even if they have previously left them.
It also includes an **admin panel** for managing users, broadcasting messages, and viewing usage statistics.

---

## Features

### User Features

* View all **channels** and **groups** you own or manage.
* Detect chats you were an **admin or creator** in, even if left.
* Simple, Telegram-native interface using keyboard buttons.
* Persian-language UI with English compatibility.

### Admin Features

* View detailed **user statistics** and activity logs.
* **Broadcast messages** to all users (forward or copy modes).
* Export user and activity reports as **Excel files**.
* Generate simple **charts** of new user growth (via Matplotlib).
* Track per-user activity and command usage.

---

## Tech Stack

* **Python 3.10+**
* **Telethon** – Telegram client library
* **SQLite3** – local user database
* **Pandas** – report generation
* **Matplotlib** – statistical visualization
* **dotenv** – environment configuration

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<yourusername>/what-chats-do-i-own.git
cd what-chats-do-i-own
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create `.env` file

Create a `.env` file in the root directory:

```env
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789,987654321
```

### 4. Run the bot

```bash
python bot.py
```

---

## Database Structure

The bot uses `SQLite` with three tables:

* **users** – stores user info and activity counters
* **user_activity** – logs user interactions
* **message_broadcasts** – tracks sent broadcast messages

---

## Commands

| Command  | Description                           |
| -------- | ------------------------------------- |
| `/start` | Start interaction and show main menu  |
| `/panel` | Open admin control panel (admin-only) |

---

## Project Structure

```
.
├── bot.py              # Main bot logic
├── users.db            # SQLite database
├── .env                # Environment variables
├── requirements.txt    # Python dependencies
└── README.md           # Project documentation
```

---

## License

This project is licensed under the **MIT License**.
You are free to modify and distribute it with proper attribution.


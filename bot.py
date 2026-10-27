

from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import (
    ReplyKeyboardMarkup, KeyboardButtonRequestPeer, KeyboardButtonRow,
    RequestPeerTypeBroadcast, RequestPeerTypeChat,
    ChatAdminRights, InputPeerUser
)
from telethon.errors import ChatAdminRequiredError, ChannelPrivateError
import asyncio
import logging
import os
import sqlite3
from datetime import datetime
import io
import pandas as pd
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
from dotenv import load_dotenv

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [x.strip() for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("please set API_ID، API_HASH و BOT_TOKEN in .env ")

bot = TelegramClient('chatlist_bot', API_ID, API_HASH)

WELCOME_MESSAGE = """ربات به شما کمک میکند کانال ها و گروه هایی که مالک یا ادمین آن هستید ببینید، حتی اگر قبلا از آنها لفت داده اید.
اطلاعات بیشتر: https://tginfo.me/how-to-find-my-chats-en/

۱. نوع چت (کانال یا گروه) را با استفاده از دکمه ها انتخاب کنید

۲. بر روی چت مورد‌نظر کلیک کنید – ربات، نام آن را ارسال میکند.

۳. روی نام کلیک کنید تا چت باز شود.

اگر چت باز نمیشود، این به معنی آن است که سرور تلگرام نمیتواند آن را نمایش دهد، و برگشتن به آن غیرممکن است.

ربات بصورت بخشی از پروژه @AlphaTeam_bots ساخته شده است"""

class Database:
    def __init__(self, db_file="users.db"):
        self.conn = sqlite3.connect(db_file)
        self.cur = self.conn.cursor()
        self.setup()
        
    def setup(self):
        """ایجاد جداول مورد نیاز"""
        self.cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TEXT,
            last_activity TEXT,
            commands_used INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
        )
        ''')
        
        self.cur.execute('''
        CREATE TABLE IF NOT EXISTS user_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            activity_type TEXT,
            timestamp TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        self.cur.execute('''
        CREATE TABLE IF NOT EXISTS message_broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            message_text TEXT,
            broadcast_type TEXT,
            sent_date TEXT,
            total_recipients INTEGER,
            successful_sends INTEGER
        )
        ''')
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name):
        """افزودن کاربر جدید به پایگاه داده"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cur.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date, last_activity) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, first_name, last_name, current_time, current_time)
        )
        self.conn.commit()
    
    def update_user_activity(self, user_id, activity_type):
        """بروزرسانی فعالیت کاربر"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.cur.execute(
            "UPDATE users SET last_activity = ?, commands_used = commands_used + 1 WHERE user_id = ?",
            (current_time, user_id)
        )
        
        self.cur.execute(
            "INSERT INTO user_activity (user_id, activity_type, timestamp) VALUES (?, ?, ?)",
            (user_id, activity_type, current_time)
        )
        self.conn.commit()
    
    def get_all_users(self):
        """دریافت تمام کاربران فعال"""
        self.cur.execute("SELECT user_id FROM users WHERE is_active = 1")
        return [row[0] for row in self.cur.fetchall()]
    
    def get_user_stats(self):
        """دریافت آمار کاربران برای پنل ادمین"""
        self.cur.execute("SELECT COUNT(*) FROM users")
        total_users = self.cur.fetchone()[0]
        
        self.cur.execute("SELECT COUNT(*) FROM users WHERE datetime(last_activity) > datetime('now', '-1 day')")
        active_users_24h = self.cur.fetchone()[0]
        
        self.cur.execute("SELECT COUNT(*) FROM users WHERE datetime(join_date) > datetime('now', '-7 days')")
        new_users_7d = self.cur.fetchone()[0]
        
        self.cur.execute("SELECT SUM(commands_used) FROM users")
        total_commands = self.cur.fetchone()[0] or 0
        
        self.cur.execute("""
        SELECT activity_type, COUNT(*) as count 
        FROM user_activity 
        GROUP BY activity_type 
        ORDER BY count DESC
        """)
        activity_stats = self.cur.fetchall()
        
        self.cur.execute("""
        SELECT date(join_date) as day, COUNT(*) as count 
        FROM users 
        WHERE datetime(join_date) > datetime('now', '-7 days')
        GROUP BY day
        ORDER BY day
        """)
        daily_new_users = self.cur.fetchall()
        
        return {
            "total_users": total_users,
            "active_users_24h": active_users_24h,
            "new_users_7d": new_users_7d,
            "total_commands": total_commands,
            "activity_stats": activity_stats,
            "daily_new_users": daily_new_users
        }
    
    def log_broadcast(self, admin_id, message_text, broadcast_type, total_recipients, successful_sends):
        """ثبت ارسال پیام گروهی"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cur.execute(
            "INSERT INTO message_broadcasts (admin_id, message_text, broadcast_type, sent_date, total_recipients, successful_sends) VALUES (?, ?, ?, ?, ?, ?)",
            (admin_id, message_text, broadcast_type, current_time, total_recipients, successful_sends)
        )
        self.conn.commit()
    
    def close(self):
        """بستن اتصال پایگاه داده"""
        self.conn.close()

db = Database()

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        rows=[
            KeyboardButtonRow(buttons=[
                KeyboardButtonRequestPeer(
                    text='لیست کانال‌هایی که ادمین آن هستم',
                    button_id=345,
                    peer_type=RequestPeerTypeBroadcast(
                        creator=False,
                        has_username=None,
                        user_admin_rights=ChatAdminRights(
                            change_info=False,
                            post_messages=False,
                            edit_messages=False,
                            delete_messages=False,
                            ban_users=True,
                            invite_users=False,
                            pin_messages=False,
                            add_admins=False,
                            anonymous=False,
                            manage_call=False,
                            other=True,
                            manage_topics=False,
                            post_stories=False,
                            edit_stories=False,
                            delete_stories=False
                        ),
                        bot_admin_rights=None
                    ),
                    max_quantity=1
                )
            ]),
            KeyboardButtonRow(buttons=[
                KeyboardButtonRequestPeer(
                    text='لیست گروه‌هایی که ادمین آن هستم',
                    button_id=456,
                    peer_type=RequestPeerTypeChat(
                        creator=False,
                        bot_participant=False,
                        has_username=None,
                        forum=None,
                        user_admin_rights=ChatAdminRights(
                            change_info=False,
                            post_messages=False,
                            edit_messages=False,
                            delete_messages=False,
                            ban_users=False,
                            invite_users=False,
                            pin_messages=False,
                            add_admins=False,
                            anonymous=False,
                            manage_call=False,
                            other=True,
                            manage_topics=False,
                            post_stories=False,
                            edit_stories=False,
                            delete_stories=False
                        ),
                        bot_admin_rights=None
                    ),
                    max_quantity=1
                )
            ]),
            KeyboardButtonRow(buttons=[
                KeyboardButtonRequestPeer(
                    text='لیست کانال‌های من',
                    button_id=123,
                    peer_type=RequestPeerTypeBroadcast(
                        creator=True,
                        has_username=None,
                        user_admin_rights=None,
                        bot_admin_rights=None
                    ),
                    max_quantity=1
                )
            ]),
            KeyboardButtonRow(buttons=[
                KeyboardButtonRequestPeer(
                    text='لیست گروه‌های من',
                    button_id=234,
                    peer_type=RequestPeerTypeChat(
                        creator=True,
                        bot_participant=False,
                        has_username=None,
                        forum=None,
                        user_admin_rights=None,
                        bot_admin_rights=None
                    ),
                    max_quantity=1
                )
            ])
        ],
        resize=False,
        single_use=False,
        selective=False,
        persistent=True,
        placeholder=None
    )

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    """مدیریت دستور /start"""
    user_id = event.sender_id
    user = await event.get_sender()
    username = user.username or ""
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    
    db.add_user(user_id, username, first_name, last_name)
    db.update_user_activity(user_id, "start_command")
    
    welcome_buttons = [
        [
            Button.url("🤖 ربات هوش مصنوعی", "https://t.me/GPTAlphaRobot")
        ],
        [   Button.url("🤖 ربات های کاربردی", "https://t.me/AlphaTeam_bots/6")]
    ]
    
    await event.respond(WELCOME_MESSAGE, buttons=welcome_buttons,link_preview=False)
    
    await event.respond("لطفا یکی از گزینه ها را انتخاب کنید:", buttons=get_main_keyboard())
    return

def is_admin(user_id):
    """بررسی آیا کاربر ادمین است یا خیر"""
    return str(user_id) in ADMIN_IDS

async def create_stats_chart(stats):
    """ایجاد نمودار آماری برای پنل ادمین و ذخیره به عنوان فایل در حافظه"""
    if not HAS_MATPLOTLIB:
        logger.warning("matplotlib is not installed, skipping the stats chart")
        return None

    if stats["daily_new_users"]:
        try:
            days = [record[0] for record in stats["daily_new_users"]]
            counts = [record[1] for record in stats["daily_new_users"]]
            
            plt.figure(figsize=(10, 6))
            plt.bar(days, counts, color='skyblue')
            plt.title('New users within last week', fontsize=14)
            plt.xlabel('Date')
            plt.ylabel('Count')
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Save the chart directly to disk
            chart_filename = "admin_stats_chart.png"
            plt.savefig(chart_filename, format='png')
            plt.close()
            
            return chart_filename
        except Exception as e:
            logger.error(f"Error creating chart: {e}")
            return None
    return None



ADMIN_STATE = {}

@bot.on(events.NewMessage(pattern='/panel'))
async def admin_panel(event):
    """پنل ادمین برای مدیریت ربات"""
    user_id = event.sender_id
    
    if not is_admin(user_id):
        await event.respond("شما دسترسی به این بخش را ندارید.")
        return
    
    ADMIN_STATE[user_id] = {"state": "main_menu"}
    
    admin_buttons = [
        [Button.text("📊 آمار کاربران"), Button.text("📤 ارسال پیام به همه")],
        [Button.text("📋 گزارش فعالیت‌ها"), Button.text("⚙️ تنظیمات")],
        [Button.text("🔙 بازگشت به منوی اصلی")]
    ]
    
    await event.respond("🔐 به پنل مدیریت خوش آمدید. لطفا گزینه مورد نظر را انتخاب کنید:", buttons=admin_buttons)

@bot.on(events.NewMessage(func=lambda e: e.is_private and e.text in [
    "📊 آمار کاربران", "📤 ارسال پیام به همه", "📋 گزارش فعالیت‌ها", 
    "⚙️ تنظیمات", "🔙 بازگشت به منوی اصلی"]))
async def handle_admin_buttons(event):
    """مدیریت دکمه‌های پنل ادمین"""
    user_id = event.sender_id
    
    if not is_admin(user_id):
        return
    
    if user_id not in ADMIN_STATE:
        ADMIN_STATE[user_id] = {"state": "main_menu"}
    
    button_text = event.text
    
    if button_text == "📊 آمار کاربران":
        ADMIN_STATE[user_id]["state"] = "stats"
        stats = db.get_user_stats()
        
        stats_text = f"""📊 **آمار ربات**

👥 **آمار کاربران:**
• کل کاربران: {stats['total_users']} نفر
• کاربران فعال در 24 ساعت گذشته: {stats['active_users_24h']} نفر
• کاربران جدید در 7 روز گذشته: {stats['new_users_7d']} نفر
• کل دستورات اجرا شده: {stats['total_commands']}

🔝 **فعالیت‌های پرکاربرد:**
"""
        for activity, count in stats["activity_stats"][:5]:
            stats_text += f"• {activity}: {count} بار\n"
        
        await event.respond(stats_text)
        

        chart_buf = await create_stats_chart(stats)
        if chart_buf:
            try:
                await event.respond("📈 نمودار کاربران جدید در هفته گذشته", 
                                file=chart_buf)
            finally:
                # create_stats_chart writes a fixed filename, so clean it up
                # instead of leaving it for the next admin to overwrite.
                if os.path.exists(chart_buf):
                    os.remove(chart_buf)
        return
    elif button_text == "📤 ارسال پیام به همه":
        ADMIN_STATE[user_id]["state"] = "broadcast_message"
        
        broadcast_buttons = [
            [Button.text("🔄 ارسال با نام (Forward)"), Button.text("📋 ارسال بدون نام (Copy)")],
            [Button.text("🔙 بازگشت")]
        ]
        
        await event.respond("""🔄 **ارسال پیام به همه کاربران**

لطفا نوع ارسال را انتخاب کنید:
- **ارسال با نام (Forward)**: پیام با نام شما ارسال می‌شود
- **ارسال بدون نام (Copy)**: پیام بدون نام ارسال می‌شود

سپس پیام خود را ارسال کنید.""", buttons=broadcast_buttons)
        return
    
    elif button_text == "📋 گزارش فعالیت‌ها":
        try:
            users_df = pd.read_sql("SELECT * FROM users", db.conn)
            activity_df = pd.read_sql("SELECT * FROM user_activity", db.conn)
            broadcast_df = pd.read_sql("SELECT * FROM message_broadcasts", db.conn)
            
            file_path = "bot_report.xlsx"
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                users_df.to_excel(writer, sheet_name='Users', index=False)
                activity_df.to_excel(writer, sheet_name='Activities', index=False)
                broadcast_df.to_excel(writer, sheet_name='Broadcasts', index=False)
            
            from telethon.tl.types import DocumentAttributeFilename
            await event.respond("📊 گزارش کامل فعالیت‌های ربات", 
                            file=file_path)
            
            import os
            os.remove(file_path)
            return
        except Exception as e:
            logging.error(f"Error generating report: {str(e)}")
            await event.respond("❌ خطا در ایجاد گزارش. لطفا بعدا تلاش کنید.")
            return
        
    elif button_text == "⚙️ تنظیمات":
        await event.respond("⚙️ بخش تنظیمات به زودی اضافه خواهد شد.")
        return
    
    elif button_text == "🔙 بازگشت به منوی اصلی":
        ADMIN_STATE[user_id]["state"] = None
        await event.respond("انتخاب کنید:", buttons=get_main_keyboard())
        return

@bot.on(events.NewMessage(func=lambda e: e.is_private and e.text in [
    "🔄 ارسال با نام (Forward)", "📋 ارسال بدون نام (Copy)", "🔙 بازگشت"]))
async def broadcast_type_handler(event):
    """مدیریت انتخاب نوع ارسال پیام گروهی"""
    user_id = event.sender_id
    
    if not is_admin(user_id):
        return
        
    if user_id not in ADMIN_STATE:
        ADMIN_STATE[user_id] = {"state": "main_menu"}
    
    button_text = event.text
    
    if button_text == "🔙 بازگشت":
        ADMIN_STATE[user_id]["state"] = "main_menu"
        admin_buttons = [
            [Button.text("📊 آمار کاربران"), Button.text("📤 ارسال پیام به همه")],
            [Button.text("📋 گزارش فعالیت‌ها"), Button.text("⚙️ تنظیمات")],
            [Button.text("🔙 بازگشت به منوی اصلی")]
        ]
        await event.respond("🔐 به پنل مدیریت خوش آمدید. لطفا گزینه مورد نظر را انتخاب کنید:", buttons=admin_buttons)
        return
    else:
        broadcast_type = "forward" if button_text == "🔄 ارسال با نام (Forward)" else "copy"
        # Store the type but don't process the same message as the broadcast message
        ADMIN_STATE[user_id] = {"state": "waiting_for_broadcast_message", "type": broadcast_type}
        await event.respond("✅ لطفا پیامی که می‌خواهید به همه کاربران ارسال شود را ارسال کنید:")
        return

@bot.on(events.NewMessage(func=lambda e: e.is_private))
async def receive_broadcast_message(event):
    """دریافت پیام برای ارسال گروهی"""
    user_id = event.sender_id
    
    if not is_admin(user_id):
        return
        
    if user_id not in ADMIN_STATE:
        return
    
    state = ADMIN_STATE[user_id].get("state")
    
    if state == "waiting_for_broadcast_message":
        # Make sure we're not processing button message text as broadcast content
        button_texts = ["🔄 ارسال با نام (Forward)", "📋 ارسال بدون نام (Copy)", "🔙 بازگشت"]
        if event.text in button_texts:
            return
            
        broadcast_type = ADMIN_STATE[user_id].get("type")
        message = event.message
        
        confirm_buttons = [
            [Button.inline("✅ بله، ارسال شود", data="confirm_broadcast")],
            [Button.inline("❌ خیر، لغو شود", data="cancel_broadcast")]
        ]
        
        ADMIN_STATE[user_id]["message"] = message
        
        await event.respond(f"""آیا از ارسال این پیام به تمام کاربران اطمینان دارید؟
        
نوع ارسال: {'با نام (Forward)' if broadcast_type == 'forward' else 'بدون نام (Copy)'}

تعداد کاربران دریافت کننده: {len(db.get_all_users())} نفر""", buttons=confirm_buttons)
        return
@bot.on(events.CallbackQuery(pattern=r"confirm_broadcast|cancel_broadcast"))
async def broadcast_confirmation(event):
    """مدیریت دکمه‌های تایید/لغو ارسال گروهی"""
    user_id = event.sender_id
    
    if not is_admin(user_id):
        await event.answer("شما دسترسی ادمین ندارید", alert=True)
        return
        
    if user_id not in ADMIN_STATE:
        await event.answer("خطا در پردازش درخواست", alert=True)
        return
    
    data = event.data.decode("utf-8")
    
    if data == "confirm_broadcast":
        message = ADMIN_STATE[user_id].get("message")
        broadcast_type = ADMIN_STATE[user_id].get("type")
        users = db.get_all_users()
        
        if not message or not broadcast_type or not users:
            await event.answer("خطا در ارسال پیام", alert=True)
            return
        
        status_message = await event.respond("🔄 در حال ارسال پیام به کاربران...")
        
        successful_sends = 0
        
        for user in users:
            try:
                if broadcast_type == "forward":
                    await bot.forward_messages(user, message)
                else:  # copy mode
                    message_text = message.message if message.message else ""
                    if message.media:
                        await bot.send_message(user, message_text, file=message.media)
                    else:
                        await bot.send_message(user, message_text)
                successful_sends += 1
                await asyncio.sleep(0.1) 
            except Exception as e:
                logger.error(f"error sending message to {user}: {e}")
        
        db.log_broadcast(
            user_id, 
            message.message, 
            broadcast_type, 
            len(users), 
            successful_sends
        )
        
        await status_message.edit(f"""✅ ارسال پیام به کاربران به پایان رسید

• تعداد کل کاربران: {len(users)} نفر
• ارسال موفق: {successful_sends} نفر
• ارسال ناموفق: {len(users) - successful_sends} نفر""")
        
        ADMIN_STATE[user_id] = {"state": "main_menu"}
        return
    
    elif data == "cancel_broadcast":
        await event.edit("❌ ارسال پیام لغو شد.")
        ADMIN_STATE[user_id] = {"state": "main_menu"}
        return


async def main():
    """تابع اصلی برای اجرای ربات"""
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot started...!")
    
    me = await bot.get_me()
    logger.info(f"Bot name: @{me.username}")
    
    await bot.run_until_disconnected()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        db.close()

import telebot
import yt_dlp
import os
import threading
import queue
import time
from dotenv import load_dotenv
# Load environment variables
load_dotenv()

# 🔐 Bot Token & Admin ID from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', ''))  # Default fallback

bot = telebot.TeleBot(BOT_TOKEN)

user_links = {}
task_queue = queue.Queue()
user_request_count = {}
user_info = {}

REQUIRED_CHANNELS = ['@odri_modz', '@Tech_Shreyansh1']

# 🔤 Static messages
MESSAGES = {
    'start': (
        "👋 Welcome Lover 💘!\n\n"
        "With this bot, you can easily Download:\n"
        "👉 Facebook videos\n"
        "👉 Instagram videos\n"
        "👉 TikTok videos (No watermark)\n\n"
        "Just send me a video link, and I’ll handle the rest. 📥\n\n"
        "🛠 Developed by: @Rana_Odri 👻\n"
        "💞 Beloved BY : @Tech_Shreyansh 💕"
    ),
    'join_required': (
        "🚫 You must join our channels to use this bot.\n\n"
        "Please join all the required channels below and press /start again."
    ),
    'choose_quality': "📥 Please select your preferred video quality:",
    'in_queue': "⏳ Your request is in the queue. Please wait a moment...",
    'downloading': "📥 Starting download...",
    'uploading': "📤 Uploading your video...",
    'no_formats': "⚠️ No downloadable video formats were found for this link.",
}

# 🚀 Start Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Inline keyboard with join buttons
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    join1 = telebot.types.InlineKeyboardButton("Join Odri Modz 👻", url="https://t.me/odri_modz")
    join2 = telebot.types.InlineKeyboardButton("Join Tech Shreyansh 🖥️", url="https://t.me/Tech_Shreyansh1")
    markup.add(join1, join2)

    bot.send_message(message.chat.id, MESSAGES['start'], reply_markup=markup)


    
# ✅ Start



# 🔄 Prevent multiple simultaneous requests and handle invalid texts/links
processing_users = set()

@bot.message_handler(func=lambda message: True)
def fallback_handler(message):
    chat_id = message.chat.id
    text = message.text.strip()

    # ⛔ Check if already processing
    if chat_id in processing_users:
        bot.reply_to(message, "⏳ Send Another Link After Finish This One.")
        return

    # ✅ Check for valid supported links
    if any(domain in text for domain in ['facebook.com', 'fb.watch', 'instagram.com', 'tiktok.com']):
        processing_users.add(chat_id)
        try:
            handle_platform_link(message)
        finally:
            processing_users.discard(chat_id)
        return

    # ❌ Invalid or unsupported text/link
    bot.reply_to(message, "⚠️ Unsupported message.\n What You Mean")





# 👨‍💼 Admin Panel
@bot.message_handler(commands=['odri'])
def admin_panel(message):
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "🚫 You are not authorized.")
        return

    if not user_request_count:
        bot.reply_to(message, "📊 No requests yet.")
        return

    total_users = len(user_request_count)
    total_requests = sum(user_request_count.values())
    report = f"📊 Total Users: {total_users}\n📦 Total Requests: {total_requests}\n\n"

    for uid, count in user_request_count.items():
        name = user_info.get(uid, "Unknown")
        report += f"👤 {name} ➜ {count} times\n"

    bot.send_message(message.chat.id, report)

# 🌐 Handlers for each platform
@bot.message_handler(func=lambda msg: 'facebook.com' in msg.text or 'fb.watch' in msg.text)
def handle_facebook(msg):
    handle_platform_link(msg)

@bot.message_handler(func=lambda msg: 'instagram.com' in msg.text)
def handle_instagram(msg):
    handle_platform_link(msg)

@bot.message_handler(func=lambda msg: 'tiktok.com' in msg.text)
def handle_tiktok(msg):
    handle_platform_link(msg)

# 🌐 Unified handler
def handle_platform_link(message):
    url = message.text.strip()

    wait_msg = bot.send_message(message.chat.id, "⏳ Please wait...")

    animation_steps = [
        "🔍 Analyzing link...",
        "🔗 Validating URL...",
        "🧠 Checking platform compatibility...",
        "📡 Connecting to server...",
        "📂 Fetching video data...",
        "📊 Parsing available formats...",
        "🎛 Filtering best quality options...",
        "🛠 Preparing video info...",
        "✅ Almost done...",
        "🚀 Ready!"
    ]

    for step in animation_steps:
        try:
            bot.edit_message_text(step, wait_msg.chat.id, wait_msg.message_id)
        except:
            pass
        time.sleep(1)

    try:
        bot.delete_message(wait_msg.chat.id, wait_msg.message_id)
    except:
        pass

    formats = get_available_formats(url)


    if not formats:
        msg = bot.reply_to(message, MESSAGES['no_formats'])
        try:
            bot.delete_message(msg.chat.id, msg.message_id)
        except:
            pass
        return

    user_links[message.chat.id] = {'url': url, 'formats': formats}

    markup = telebot.types.InlineKeyboardMarkup(row_width=3)
    buttons = [telebot.types.InlineKeyboardButton(f"{f['height']}p", callback_data=str(f['height'])) for f in formats]
    markup.add(*buttons)

    bot.send_message(message.chat.id, MESSAGES['choose_quality'], reply_markup=markup)

# 📦 Quality Selection
@bot.callback_query_handler(func=lambda call: True)
def handle_quality_selection(call):
    chat_id = call.message.chat.id
    selection = call.data
    info = user_links.get(chat_id)

    if not info:
        return

    selected_fmt = next((f for f in info['formats'] if str(f['height']) == selection), None)
    if selected_fmt:
        uid = chat_id
        uname = call.from_user.username or f"{call.from_user.first_name} {call.from_user.last_name or ''}".strip()
        user_request_count[uid] = user_request_count.get(uid, 0) + 1
        user_info[uid] = uname

        task_queue.put((call.message, info['url'], selected_fmt['height']))

        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass

        wait_msg = bot.send_message(chat_id, MESSAGES['in_queue'])
        time.sleep(2)
        try:
            bot.delete_message(chat_id, wait_msg.message_id)
        except:
            pass

# 🧠 Get formats
def get_available_formats(url):
    try:
        ydl_opts = {'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            seen = set()
            for f in info['formats']:
                if f.get('height') and f['height'] not in seen:
                    seen.add(f['height'])
                    formats.append({
                        'height': f['height'],
                        'format_id': f['format_id']
                    })
            return sorted(formats, key=lambda x: x['height'])
    except Exception as e:
        print(f"[Format Error] {e}")
        return []

# 🧵 Worker Thread
def worker():
    while True:
        try:
            message, url, height = task_queue.get()
            download_and_send_video(message, url)
        except Exception as e:
            print(f"[Worker Error] {e}")

threading.Thread(target=worker, daemon=True).start()




def upload_and_track_progress(chat_id, file_path, message_id):
    try:
        total_size = os.path.getsize(file_path)
        start_time = time.time()
        uploaded = 0
        total_blocks = 12

        # Create thread-safe shared variable
        upload_progress = {'uploaded': 0}

        def track_upload():
            while upload_progress['uploaded'] < total_size:
                elapsed = time.time() - start_time
                speed = upload_progress['uploaded'] / elapsed if elapsed > 0 else 0
                eta = (total_size - upload_progress['uploaded']) / speed if speed > 0 else 0

                percent = upload_progress['uploaded'] / total_size * 100
                filled_blocks = int(percent / 100 * total_blocks)
                bar = "🟩" * filled_blocks + "⬜️" * (total_blocks - filled_blocks)

                speed_text = f"{speed / 1024:.1f} KB/s"
                eta_text = f"{int(eta)}s"

                text = (
                    f"⏫ *Uploading...*\n"
                    f"{bar} `{percent:.1f}%`\n"
                    f"⚡️ Speed: `{speed_text}`\n"
                    f"⏳ ETA: `{eta_text}`"
                )
                try:
                    bot.edit_message_text(chat_id, message_id, text, parse_mode="Markdown")
                except:
                    pass

                time.sleep(1)

        # Start progress tracking thread
        tracker_thread = threading.Thread(target=track_upload, daemon=True)
        tracker_thread.start()

        # Start actual upload
        with open(file_path, 'rb') as video:
            data = b''
            chunk_size = 1024 * 64
            while True:
                chunk = video.read(chunk_size)
                if not chunk:
                    break
                data += chunk
                upload_progress['uploaded'] += len(chunk)

        with open(file_path, 'rb') as video:
            bot.send_video(chat_id, video)

    except Exception as e:
        try:
            bot.edit_message_text(chat_id, message_id, f"⚠️ Upload Error: {e}")
        except:
            pass

# 📥 Download & Upload


def download_and_send_video(message, url):
    chat_id = message.chat.id
    progress_msg = bot.send_message(chat_id, MESSAGES['downloading'])
    file_path = f"{chat_id}_video.mp4"

    def progress_hook(d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 1)
            percent = downloaded / total * 100

            total_blocks = 12
            filled_blocks = int(percent / 100 * total_blocks)
            bar = "🟩" * filled_blocks + "⬜️" * (total_blocks - filled_blocks)

            speed = d.get('speed', 0)
            eta = d.get('eta', 0)

            speed_text = f"{speed / 1024:.1f} KB/s" if speed else "N/A"
            eta_text = f"{eta}s" if eta else "N/A"

            text = (
                f"📥 *Downloading...*\n"
                f"{bar} `{percent:.1f}%`\n"
                f"⚡️ Speed: `{speed_text}`\n"
                f"⏳ ETA: `{eta_text}`"
            )

            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg.message_id,
                    text=text,
                    parse_mode='Markdown'
                )
            except:
                pass

    try:
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': file_path,
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'quiet': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        bot.delete_message(chat_id, progress_msg.message_id)

        # 📤 Uploading animation
        uploading_msg = bot.send_message(chat_id, "⏫ *Uploading...*\n⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️", parse_mode="Markdown")
        total_blocks = 12
        for i in range(1, total_blocks + 1):
            bar = "🟩" * i + "⬜️" * (total_blocks - i)
            percent_text = f"{(i / total_blocks) * 100:.1f}%"
            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=uploading_msg.message_id,
                    text=f"⏫ *Uploading...*\n{bar} `{percent_text}`",
                    parse_mode="Markdown"
                )
            except:
                pass
            time.sleep(0.5)

        with open(file_path, 'rb') as video:
            bot.send_chat_action(chat_id, 'upload_video')
            bot.send_video(chat_id, video)

        try:
            bot.delete_message(chat_id, uploading_msg.message_id)
        except:
            pass

        os.remove(file_path)

    except Exception as e:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg.message_id,
                text=f"⚠️ Error: {str(e)}"
            )
        except:
            pass

# ✅ Start polling
bot.polling("🥳 Bot Started........")

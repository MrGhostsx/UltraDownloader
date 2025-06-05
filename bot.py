import telebot
import yt_dlp
import os
import threading
import queue
import time
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

# 🔐 Configuration from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN', '') # Add Your Bot Token
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', ''))  # Default fallback

if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN environment variable set")

bot = telebot.TeleBot(BOT_TOKEN)

# Data storage
user_links = {}
task_queue = queue.Queue()
user_request_count = defaultdict(int)
user_info = {}
active_users = set()  # Track active users
processing_users = set()  # Track currently processing users

REQUIRED_CHANNELS = ['@odri_modz', '@Tech_Shreyansh1']

# 🔤 Enhanced messages with better formatting
MESSAGES = {
    'start': """
🌟 *Welcome to Video Downloader Bot!* 🌟

With this bot, you can download high-quality videos from:
- Facebook 🟦
- Instagram 📷
- TikTok 🎵

✨ *Features:*
✅ No watermark for TikTok
✅ Multiple quality options
✅ Fast downloads

🛠 *Developer:* @Rana_Odri
💖 *Sponsored by:* @Tech_Shreyansh

Just send me a video link to get started!
""",
    'join_required': """
🔒 *Access Restricted* 🔒

To use this bot, please join our official channels first:

📢 @odri_modz - For latest updates
💻 @Tech_Shreyansh1 - Tech tips & tricks

After joining, press /start again.
""",
    'choose_quality': "🎚 *Select Video Quality:*\nChoose from the options below:",
    'in_queue': "⏳ Your request is in queue. Please wait...",
    'downloading': "📥 *Download Started*\nPreparing your video...",
    'uploading': "📤 *Uploading...*\nYour video will be ready soon!",
    'no_formats': "⚠️ *Error*\nNo downloadable formats found for this link.",
    'processing': "🔄 Processing your request...",
    'invalid_link': "❌ *Invalid Link*\nPlease send a valid Facebook, Instagram, or TikTok URL.",
    'admin_stats': """
📊 *Admin Statistics*

👥 Total Users: {}
🟢 Active Users: {}
📥 Total Requests: {}

⭐ *Top Users* ⭐
{}
""",
    'user_stats': "👤 {} - {} requests",
    'rate_limit': "🚫 *Too Many Requests*\nPlease wait before sending another link."
}

MAX_REQUESTS_PER_MINUTE = 3

# 🎨 Helper function for progress bars
def create_progress_bar(percent, total_blocks=10):
    filled = int(percent / 100 * total_blocks)
    return "🟩" * filled + "⬜️" * (total_blocks - filled)

# 🚀 Start Command with enhanced keyboard
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    active_users.add(user_id)  # Track active user
    
    # Store user info
    user_info[user_id] = {
        'username': message.from_user.username,
        'name': f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip(),
        'join_date': time.strftime("%Y-%m-%d %H:%M:%S")
    }

    # Check channel membership
    for channel in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                markup = telebot.types.InlineKeyboardMarkup()
                join_btn = telebot.types.InlineKeyboardButton("Join Channels", url=f"https://t.me/{channel[1:]}")
                markup.add(join_btn)
                bot.send_message(message.chat.id, MESSAGES['join_required'], reply_markup=markup)
                return
        except Exception as e:
            print(f"Error checking channel membership: {e}")

    # Create welcome message with buttons
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn1 = telebot.types.InlineKeyboardButton("📘 Tutorial", callback_data="tutorial")
    btn2 = telebot.types.InlineKeyboardButton("🛠 Support", url="t.me/Rana_Odri")
    btn3 = telebot.types.InlineKeyboardButton("⭐ Rate", callback_data="rate")
    markup.add(btn1, btn2, btn3)
    
    bot.send_message(
        message.chat.id,
        MESSAGES['start'],
        reply_markup=markup,
        parse_mode="Markdown"
    )

# 🔄 Main handler with rate limiting
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text.strip()

    # Rate limiting
    current_time = time.time()
    if user_id in user_request_count:
        last_request_time = user_request_count[user_id].get('last_request', 0)
        if current_time - last_request_time < 60:  # 1 minute window
            count = user_request_count[user_id].get('count', 0)
            if count >= MAX_REQUESTS_PER_MINUTE:
                bot.reply_to(message, MESSAGES['rate_limit'])
                return
            user_request_count[user_id]['count'] = count + 1
        else:
            user_request_count[user_id] = {'count': 1, 'last_request': current_time}
    else:
        user_request_count[user_id] = {'count': 1, 'last_request': current_time}

    # Check if already processing
    if chat_id in processing_users:
        bot.reply_to(message, "⏳ Please wait until your current download completes.")
        return

    # Validate URL
    if not any(domain in text for domain in ['facebook.com', 'fb.watch', 'instagram.com', 'tiktok.com']):
        bot.reply_to(message, MESSAGES['invalid_link'])
        return

    processing_users.add(chat_id)
    try:
        handle_platform_link(message)
    except Exception as e:
        print(f"Error processing message: {e}")
        bot.reply_to(message, f"⚠️ An error occurred: {str(e)}")
    finally:
        processing_users.discard(chat_id)

# 🌐 Platform link handler with better animations
def handle_platform_link(message):
    url = message.text.strip()
    chat_id = message.chat.id
    
    # Send initial processing message
    processing_msg = bot.send_message(chat_id, MESSAGES['processing'])
    
    # Animation sequence
    steps = [
        "🔍 Analyzing link...",
        "🔗 Validating URL...",
        "📡 Connecting to source...",
        "📂 Fetching video data...",
        "🎚 Checking available formats...",
        "⚙️ Preparing download options...",
        "✅ Ready!"
    ]
    
    for step in steps:
        try:
            bot.edit_message_text(step, chat_id, processing_msg.message_id)
            time.sleep(0.7)
        except:
            pass

    # Get available formats
    formats = get_available_formats(url)
    if not formats:
        bot.edit_message_text(MESSAGES['no_formats'], chat_id, processing_msg.message_id)
        return

    user_links[chat_id] = {'url': url, 'formats': formats}
    
    # Create quality selection keyboard
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        telebot.types.InlineKeyboardButton(
            f"{f['height']}p {'🔥' if i == 0 else ''}",
            callback_data=str(f['height'])
        ) 
        for i, f in enumerate(formats[:4])  # Show max 4 quality options
    ]
    markup.add(*buttons)
    
    # Add help button
    markup.add(telebot.types.InlineKeyboardButton("ℹ️ Help", callback_data="quality_help"))
    
    bot.edit_message_text(
        MESSAGES['choose_quality'],
        chat_id,
        processing_msg.message_id,
        reply_markup=markup
    )

# 📦 Quality selection handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    
    if call.data == "quality_help":
        bot.answer_callback_query(call.id, "Higher numbers mean better quality but larger file size")
        return
    
    if call.data == "tutorial":
        bot.answer_callback_query(call.id, "Coming soon!")
        return
    
    # Process quality selection
    info = user_links.get(chat_id)
    if not info:
        bot.answer_callback_query(call.id, "Session expired. Please send the link again.")
        return
    
    selected_fmt = next((f for f in info['formats'] if str(f['height']) == call.data), None)
    if selected_fmt:
        task_queue.put((call.message, info['url'], selected_fmt['height']))
        bot.answer_callback_query(call.id, f"Added to queue: {selected_fmt['height']}p")
        
        # Show queue position
        queue_size = task_queue.qsize()
        if queue_size > 1:
            bot.send_message(chat_id, f"⏳ Your position in queue: {queue_size}")

# 🧠 Get available formats with better error handling
def get_available_formats(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'simulate': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            seen = set()
            
            for f in info.get('formats', []):
                if f.get('height') and f['height'] not in seen:
                    seen.add(f['height'])
                    formats.append({
                        'height': f['height'],
                        'format_id': f['format_id'],
                        'filesize': f.get('filesize', 0)
                    })
            
            # Sort by quality and filter unrealistic formats
            formats = sorted(
                [f for f in formats if 100 <= f['height'] <= 2160],
                key=lambda x: x['height'],
                reverse=True
            )
            
            return formats[:4]  # Return max 4 quality options
            
    except Exception as e:
        print(f"Error getting formats: {e}")
        return []

# 📥 Download function with improved progress tracking
def download_and_send_video(message, url, quality):
    chat_id = message.chat.id
    file_path = f"downloads/{chat_id}_{int(time.time())}.mp4"
    
    # Create downloads directory if not exists
    os.makedirs("downloads", exist_ok=True)
    
    # Send initial download message
    progress_msg = bot.send_message(chat_id, MESSAGES['downloading'])
    
    try:
        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
            'outtmpl': file_path,
            'merge_output_format': 'mp4',
            'quiet': True,
            'progress_hooks': [lambda d: download_progress(d, chat_id, progress_msg.message_id)],
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }]
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Upload the file
        upload_video(chat_id, file_path, progress_msg.message_id)
        
    except Exception as e:
        print(f"Download error: {e}")
        bot.edit_message_text(f"❌ Download failed: {str(e)}", chat_id, progress_msg.message_id)
    finally:
        # Clean up
        if os.path.exists(file_path):
            os.remove(file_path)

def download_progress(d, chat_id, message_id):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%').strip('%')
        try:
            percent = float(percent)
        except:
            percent = 0
            
        bar = create_progress_bar(percent)
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        
        text = f"""
📥 *Downloading...*
{bar} `{percent:.1f}%`
        
⚡️ Speed: `{speed}`
⏳ ETA: `{eta}`
"""
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="Markdown"
            )
        except:
            pass

def upload_video(chat_id, file_path, progress_msg_id):
    try:
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # in MB
        if file_size > 50:  # Telegram file size limit is 50MB
            bot.edit_message_text(
                "⚠️ File too large (max 50MB)",
                chat_id,
                progress_msg_id
            )
            return
        
        # Start upload progress
        bot.edit_message_text(
            MESSAGES['uploading'],
            chat_id,
            progress_msg_id
        )
        
        # Send video with progress tracking
        with open(file_path, 'rb') as video_file:
            bot.send_chat_action(chat_id, 'upload_video')
            bot.send_video(
                chat_id,
                video_file,
                supports_streaming=True,
                timeout=100
            )
        
        # Clean up
        bot.delete_message(chat_id, progress_msg_id)
        
    except Exception as e:
        print(f"Upload error: {e}")
        bot.edit_message_text(
            f"⚠️ Upload failed: {str(e)}",
            chat_id,
            progress_msg_id
        )

# 👨‍💼 Enhanced Admin Panel
@bot.message_handler(commands=['odri'])
def admin_panel(message):
    if message.from_user.id != ADMIN_USER_ID:
        bot.reply_to(message, "🚫 Access denied")
        return
    
    if not user_request_count:
        bot.reply_to(message, "📊 No user data available yet")
        return
    
    total_users = len(user_info)
    active_count = len(active_users)
    total_requests = sum(v['count'] for v in user_request_count.values() if isinstance(v, dict))
    
    # Get top 5 users
    top_users = sorted(
        [(uid, data['count']) for uid, data in user_request_count.items() if isinstance(data, dict)],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    user_list = "\n".join(
        [f"{i+1}. {user_info.get(uid, {}).get('name', 'Unknown')} - {count} requests"
         for i, (uid, count) in enumerate(top_users)]
    )
    
    stats = MESSAGES['admin_stats'].format(
        total_users,
        active_count,
        total_requests,
        user_list
    )
    
    bot.reply_to(message, stats, parse_mode="Markdown")

# 🧵 Worker thread for processing queue
def worker():
    while True:
        try:
            message, url, quality = task_queue.get()
            download_and_send_video(message, url, quality)
            task_queue.task_done()
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(5)

# Start worker threads
for i in range(3):  # 3 worker threads
    t = threading.Thread(target=worker, daemon=True)
    t.start()

# Start the bot
if __name__ == '__main__':
    print("🥳 Bot Started........")
    bot.infinity_polling()

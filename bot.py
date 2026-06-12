import os
import feedparser
import requests
import time
import re
import json
from datetime import datetime
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# ==================== تنظیمات از Environment Variables ====================
SUBREDDIT = os.environ.get("SUBREDDIT", "SquaredCircle")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# خواندن CHAT_IDS از Secrets (امن) با مقدار پیش‌فرض
raw_chat_ids = os.environ.get("CHAT_IDS", "")
if raw_chat_ids:
    CHAT_IDS = [int(x.strip()) for x in raw_chat_ids.split(",") if x.strip()]
else:
    # مقدار پیش‌فرض (اگر در Secrets تنظیم نشده بود)
    CHAT_IDS = [8956194322, 1386381987]

translator = GoogleTranslator(source='auto', target='fa')
LAST_POST_FILE = "last_post.txt"

# چک کردن اولیه
print(f"🤖 شروع ربات Reddit به تلگرام - {datetime.now()}")
print(f"ساب‌ردیت: r/{SUBREDDIT}")
print(f"چت آیدی‌ها: {CHAT_IDS}")
print(f"BOT_TOKEN موجود: {'✅ بله' if BOT_TOKEN else '❌ خیر'}")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN تنظیم نشده!")
    exit(1)
if not CHAT_IDS:
    print("❌ CHAT_IDS تنظیم نشده!")
    exit(1)

# =================================================

def get_last_post():
    """خواندن آخرین پست ذخیره شده از فایل"""
    if os.path.exists(LAST_POST_FILE):
        with open(LAST_POST_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def save_last_post(post_id):
    """ذخیره آخرین پست در فایل"""
    with open(LAST_POST_FILE, "w", encoding="utf-8") as f:
        f.write(post_id)

def clean_html(text):
    """پاک کردن HTML و متن‌های اضافی"""
    if not text:
        return ""
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text()
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'submitted by\s+/?u?/\w+', '', text, flags=re.I)
    text = re.sub(r'/?u/\w+', '', text, flags=re.I)
    text = re.sub(r'\|\s*\d+\s*votes?', '', text, flags=re.I)
    text = re.sub(r'\d+\s*comments?', '', text, flags=re.I)
    text = re.sub(r'From the \w+ community on Reddit:', '', text, flags=re.I)
    return text.strip()

def extract_image_url(entry):
    """استخراج آدرس تصویر از پست"""
    # از summary
    if hasattr(entry, 'summary'):
        soup = BeautifulSoup(entry.summary, 'html.parser')
        img = soup.find('img')
        if img and img.get('src'):
            return img['src']
    
    # از لینک‌ها
    if hasattr(entry, 'links'):
        for link in entry.links:
            href = link.get('href', '').lower()
            if any(ext in href for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                return link.get('href')
    
    # جستجو با regex
    if hasattr(entry, 'summary'):
        urls = re.findall(r'https?://[^\s]+?\.(?:jpg|jpeg|png|gif|webp)', entry.summary, re.I)
        if urls:
            return urls[0]
    
    return None

def translate_text(text):
    """ترجمه متن به فارسی"""
    try:
        text = clean_html(text)
        if not text or len(text) < 5:
            return ""
        if len(text) > 1400:
            text = text[:1400] + "..."
        return translator.translate(text)
    except Exception as e:
        print(f"⚠️ خطای ترجمه: {e}")
        return text[:500] if text else ""

def send_to_user(chat_id, title, summary, link, image_url=None):
    """ارسال پست به تلگرام با دکمه شیشه‌ای"""
    
    message = f"📝 {title}\n\n"
    
    if summary and len(summary) > 5:
        message += f"{summary}\n\n"
    
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "📖 مشاهده پست",
                    "url": link
                }
            ],
            [
                {
                    "text": "💬 کامنت‌ها",
                    "url": link
                }
            ],
            [
                {
                    "text": f"🔥 r/{SUBREDDIT}",
                    "url": f"https://reddit.com/r/{SUBREDDIT}"
                }
            ]
        ]
    }
    
    # محدودیت کپشن عکس تلگرام (حداکثر 1024 کاراکتر)
    photo_caption = message
    if len(photo_caption) > 1000:
        photo_caption = photo_caption[:1000] + "..."
    
    # ارسال همراه عکس
    if image_url:
        try:
            photo_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            
            data = {
                "chat_id": chat_id,
                "photo": image_url,
                "caption": photo_caption,
                "reply_markup": json.dumps(keyboard)
            }
            
            response = requests.post(
                photo_url,
                data=data,
                timeout=25
            )
            
            if response.ok:
                return True
                
        except Exception as e:
            print(f"⚠️ خطا در ارسال عکس: {e}")
    
    # ارسال متنی
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        data = {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
            "reply_markup": json.dumps(keyboard)
        }
        
        response = requests.post(
            url,
            data=data,
            timeout=25
        )
        
        return response.ok
        
    except Exception as e:
        print(f"❌ خطا در ارسال به {chat_id}: {e}")
        return False

def get_new_posts():
    """گرفتن همه پست‌های جدید از آخرین اجرای ربات (نسخه دیباگ)"""
    url = f"https://www.reddit.com/r/{SUBREDDIT}/.rss"
    feed = feedparser.parse(url)
    
    if not feed.entries:
        print("RSS EMPTY")
        return []
    
    last_saved = get_last_post()
    
    print("========== DEBUG ==========")
    print("LAST SAVED:", repr(last_saved))
    
    for i, entry in enumerate(feed.entries[:15]):
        print(f"{i+1}. {entry.id}")
        print(f"   {entry.title}")
    print("===========================")
    
    new_posts = []
    
    for entry in feed.entries:
        title_lower = entry.title.lower()
        
        # رد کردن پست‌های پین شده
        if any(word in title_lower for word in [
            'pinned',
            'daily discussion',
            'discussion thread',
            "wreddit's daily"
        ]):
            continue
        
        # اگر به پست ذخیره شده رسیدیم، متوقف شو
        if entry.id == last_saved:
            print("FOUND LAST SAVED -> STOP")
            break
        
        new_posts.append({
            'id': entry.id,
            'title': entry.title,
            'link': entry.link,
            'summary': entry.get('summary', ''),
            'image_url': extract_image_url(entry)
        })
    
    print("NEW POSTS FOUND:", len(new_posts))
    
    return list(reversed(new_posts))

def main():
    """تابع اصلی"""
    new_posts = get_new_posts()
    
    if not new_posts:
        print("✅ پست جدیدی وجود ندارد")
        return
    
    print(f"🆕 تعداد پست‌های جدید: {len(new_posts)}")
    
    success_posts = []
    
    for post in new_posts:
        print(f"🔄 ارسال: {post['title'][:60]}...")
        
        title_fa = translate_text(post['title'])
        summary_fa = translate_text(post['summary'])
        
        success_count = 0
        
        for chat_id in CHAT_IDS:
            if send_to_user(
                chat_id,
                title_fa,
                summary_fa,
                post['link'],
                post['image_url']
            ):
                success_count += 1
            
            time.sleep(1.5)
        
        if success_count > 0:
            success_posts.append(post)
    
    if success_posts:
        save_last_post(success_posts[-1]["id"])
        print(f"💾 آخرین پست ذخیره شد: {success_posts[-1]['id']}")
    
    print("🎉 پایان")

if __name__ == "__main__":
    main()

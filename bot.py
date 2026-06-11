import os
import feedparser
import requests
import time
import re
from datetime import datetime
from deep_translator import GoogleTranslator

# تنظیمات
SUBREDDIT = os.environ.get("SUBREDDIT", "SquaredCircle")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
LAST_POSTS_FILE = "last_posts.txt"

# مترجم
translator = GoogleTranslator(source='auto', target='fa')

def get_last_post_ids():
    if os.path.exists(LAST_POSTS_FILE):
        with open(LAST_POSTS_FILE, 'r') as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_post_id(post_id):
    with open(LAST_POSTS_FILE, 'a') as f:
        f.write(f"{post_id}\n")

def clean_text(text):
    """تمیز کردن متن از تگ‌های HTML و کاراکترهای اضافی"""
    # حذف تگ‌های HTML
    text = re.sub('<[^<]+?>', '', text)
    # حذف کدهای HTML مثل &#32;
    text = re.sub(r'&#\d+;', '', text)
    # جایگزینی کاراکترهای خاص
    text = text.replace('&#32;', ' ')
    text = text.replace('&quot;', '"')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    # حذف فاصله‌های اضافی
    text = re.sub(r'\s+', ' ', text)
    # حذف عبارت‌های اضافی
    text = re.sub(r'submitted by\s+/\u\w+', '', text)
    text = re.sub(r'\[link\]\s*\[comments\]', '', text)
    return text.strip()

def translate_text(text):
    """ترجمه متن با مدیریت خطا"""
    try:
        text = clean_text(text)
        if not text or len(text) < 5:
            return ""
        if len(text) > 3000:
            text = text[:3000] + "..."
        translated = translator.translate(text)
        return translated
    except Exception as e:
        print(f"خطا در ترجمه: {e}")
        return text

def get_new_posts():
    url = f"https://www.reddit.com/r/{SUBREDDIT}/.rss"
    feed = feedparser.parse(url)
    
    last_ids = get_last_post_ids()
    new_posts = []
    
    for entry in feed.entries[:10]:
        if entry.id not in last_ids:
            new_posts.append({
                'id': entry.id,
                'title': entry.title,
                'link': entry.link,
                'summary': entry.summary
            })
    return new_posts

def send_to_telegram(title, summary, link):
    """ارسال پست ترجمه شده با فرمت بهتر"""
    # ساخت پیام خواناتر
    message_parts = []
    
    if title:
        message_parts.append(f"📝 **{title}**")
    
    if summary and len(summary) > 10:
        # خلاصه متن را کوتاه‌تر می‌کنیم
        if len(summary) > 800:
            summary = summary[:800] + "..."
        message_parts.append(f"\n{summary}")
    
    message_parts.append(f"\n🔗 [مشاهده در ردیت]({link})")
    
    message = "".join(message_parts)
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    
    try:
        response = requests.post(url, data=data, timeout=30)
        return response.ok
    except Exception as e:
        print(f"خطا در ارسال: {e}")
        # اگر Markdown مشکل داشت، بدون فرمت بفرست
        try:
            data['parse_mode'] = None
            response = requests.post(url, data=data, timeout=30)
            return response.ok
        except:
            return False

def main():
    print(f"🤖 ربات در حال اجرا - {datetime.now()}")
    print(f"در حال بررسی سابردیت r/{SUBREDDIT}")
    
    posts = get_new_posts()
    print(f"پست‌های جدید: {len(posts)}")
    
    for post in posts:
        print(f"در حال ترجمه: {post['title'][:40]}...")
        
        # ترجمه عنوان و متن
        title_fa = translate_text(post['title'])
        summary_fa = translate_text(post['summary'])
        
        if title_fa or summary_fa:
            print(f"ارسال به تلگرام...")
            if send_to_telegram(title_fa, summary_fa, post['link']):
                print("✓ ارسال شد")
                save_post_id(post['id'])
            else:
                print("✗ خطا در ارسال")
        else:
            print("✗ متنی برای ارسال وجود ندارد")
        
        time.sleep(2)
    
    print("پایان")

if __name__ == "__main__":
    main()

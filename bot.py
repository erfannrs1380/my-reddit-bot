import os
import feedparser
import requests
import time
import re
from datetime import datetime
from deep_translator import GoogleTranslator

# تنظیمات
SUBREDDIT = os.environ.get("SUBREDDIT", "AskReddit")
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

def clean_html(text):
    """حذف تگ‌های HTML و کاراکترهای اضافی"""
    text = re.sub('<[^<]+?>', '', text)
    text = re.sub(r'&#\d+;', '', text)
    text = text.replace('&#32;', ' ')
    return text.strip()

def translate_text(text):
    """ترجمه از انگلیسی به فارسی"""
    try:
        text = clean_html(text)
        if len(text) > 4000:
            text = text[:4000] + "..."
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
    """ارسال پست ترجمه شده به تلگرام"""
    message = f"📝 {title}\n\n{summary}\n\n🔗 {link}"
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'disable_web_page_preview': True
    }
    
    try:
        response = requests.post(url, data=data, timeout=30)
        return response.ok
    except Exception as e:
        print(f"خطا در ارسال: {e}")
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
        
        print(f"ارسال به تلگرام...")
        if send_to_telegram(title_fa, summary_fa, post['link']):
            print("✓ ارسال شد")
            save_post_id(post['id'])
        else:
            print("✗ خطا در ارسال")
        
        time.sleep(2)
    
    print("پایان")

if __name__ == "__main__":
    main()

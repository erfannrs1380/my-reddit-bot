import os
import feedparser
import requests
import time
import re
from datetime import datetime
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

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

def clean_html(text):
    """پاک کردن کامل HTML با BeautifulSoup"""
    if not text:
        return ""
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text()
    text = re.sub(r'&#\d+;', '', text)
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    # حذف عبارت "submitted by /u/username"
    text = re.sub(r'submitted by\s+/\w+', '', text)
    text = re.sub(r'\[link\]\s*\[comments\]', '', text)
    text = text.strip()
    return text

def extract_image_url(entry):
    """استخراج آدرس عکس از پست (اگه وجود داشته باشه)"""
    # اول چک کن توی summary عکس هست؟
    if hasattr(entry, 'summary'):
        soup = BeautifulSoup(entry.summary, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
    
    # چک کن توی لینک‌ها عکس هست؟
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.get('type') and 'image' in link.get('type', ''):
                return link.get('href')
            if link.get('href') and any(ext in link['href'].lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                return link['href']
    
    return None

def translate_text(text):
    """ترجمه متن به فارسی"""
    try:
        text = clean_html(text)
        if not text or len(text) < 5:
            return ""
        if len(text) > 1500:
            text = text[:1500] + "..."
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
            # استخراج آدرس عکس
            image_url = extract_image_url(entry)
            
            new_posts.append({
                'id': entry.id,
                'title': entry.title,
                'link': entry.link,
                'summary': entry.summary,
                'image_url': image_url
            })
    return new_posts

def send_to_telegram(title, summary, link, image_url=None):
    """ارسال پست با عکس و دکمه شیشه‌ای"""
    
    # ساخت پیام متنی
    message = f"📝 {title}\n\n{summary}"
    
    # اگر عکس داریم، اول عکس رو بفرست بعد متن رو
    if image_url:
        # ارسال عکس با caption (توضیح زیر عکس)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        data = {
            'chat_id': CHAT_ID,
            'photo': image_url,
            'caption': message,
            'parse_mode': 'Markdown'
        }
        try:
            response = requests.post(url, data=data, timeout=30)
            if not response.ok:
                # اگه ارسال عکس failed، برگرد به ارسال متن ساده
                return send_text_message(message, link)
            # ارسال دکمه جداگانه بعد از عکس
            return send_inline_button(link)
        except:
            return send_text_message(message, link)
    else:
        # بدون عکس، فقط متن با دکمه
        return send_text_message(message, link)

def send_text_message(message, link):
    """ارسال پیام متنی ساده"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': message,
        'disable_web_page_preview': True
    }
    try:
        response = requests.post(url, data=data, timeout=30)
        if response.ok:
            # بعد از متن، دکمه رو بفرست
            return send_inline_button(link)
        return False
    except:
        return False

def send_inline_button(link):
    """ارسال دکمه شیشه‌ای با لینک"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # ساخت دکمه شیشه‌ای
    keyboard = {
        "inline_keyboard": [
            [{"text": "🔗 مشاهده در ردیت", "url": link}]
        ]
    }
    
    import json
    data = {
        'chat_id': CHAT_ID,
        'text': "👇 برای مشاهده پست کلیک کن",
        'reply_markup': json.dumps(keyboard)
    }
    
    try:
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
        
        title_fa = translate_text(post['title'])
        summary_fa = translate_text(post['summary']) if post['summary'] else "(بدون توضیح)"
        
        if title_fa:
            print(f"عکس دارد: {'بله' if post['image_url'] else 'خیر'}")
            
            if send_to_telegram(title_fa, summary_fa, post['link'], post['image_url']):
                print("✓ ارسال شد")
                save_post_id(post['id'])
            else:
                print("✗ خطا در ارسال")
        else:
            print("✗ متنی برای ترجمه وجود ندارد")
        
        time.sleep(2)
    
    print("پایان")

if __name__ == "__main__":
    main()

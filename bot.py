import os
import feedparser
import requests
import time
import re
from datetime import datetime
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

SUBREDDIT = os.environ.get("SUBREDDIT", "SquaredCircle")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

CHAT_IDS = [
    8956194322,
    1386381987
]

translator = GoogleTranslator(source='auto', target='fa')

# ذخیره آخرین لینک ارسال شده (در حافظه همین اجرا)
last_sent_link = None

def clean_html(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text()
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'submitted by\s+/\w+', '', text)
    text = re.sub(r'/u/\w+', '', text)
    text = re.sub(r'u/\w+', '', text)
    text = re.sub(r'\|\s*\d+\s*votes?\s*', '', text)
    text = re.sub(r'\d+\s*comments?', '', text)
    text = text.strip()
    return text

def extract_image_url(entry):
    if hasattr(entry, 'summary'):
        soup = BeautifulSoup(entry.summary, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
    
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.get('type') and 'image' in link['type']:
                return link.get('href')
            if link.get('href'):
                href = link['href'].lower()
                if any(ext in href for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    return link['href']
    
    if hasattr(entry, 'summary'):
        urls = re.findall(r'(https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp))', entry.summary, re.IGNORECASE)
        if urls:
            return urls[0]
    
    return None

def translate_text(text):
    try:
        text = clean_html(text)
        if not text or len(text) < 5:
            return ""
        if len(text) > 1500:
            text = text[:1500] + "..."
        return translator.translate(text)
    except:
        return text

def get_latest_normal_post():
    """گرفتن آخرین پست معمولی (نه پین شده)"""
    url = f"https://www.reddit.com/r/{SUBREDDIT}/.rss"
    feed = feedparser.parse(url)
    
    for entry in feed.entries[:15]:  # ۱۵ تای اول رو چک کن
        # بررسی نکردن پست‌های پین شده
        if hasattr(entry, 'sticky') and entry.sticky == 'true':
            print(f"⏭️ رد شد (پست پین شده): {entry.title[:40]}...")
            continue
        
        return {
            'title': entry.title,
            'link': entry.link,
            'summary': entry.summary,
            'image_url': extract_image_url(entry),
            'published': entry.get('published', '')
        }
    
    return None

def send_notification(chat_id, message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message,
        'disable_web_page_preview': True
    }
    try:
        requests.post(url, data=data, timeout=30)
    except:
        pass

def send_to_user(chat_id, title, summary, link, image_url=None):
    link_text = f"[(لینک)]({link})"
    message = f"📝 {title}\n\n"
    if summary and len(summary) > 5:
        message += f"{summary}\n\n"
    message += link_text
    
    if image_url:
        photo_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        photo_data = {
            'chat_id': chat_id,
            'photo': image_url,
            'caption': message,
            'parse_mode': 'Markdown'
        }
        try:
            requests.post(photo_url, data=photo_data, timeout=30)
            return True
        except:
            pass
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    try:
        requests.post(url, data=data, timeout=30)
        return True
    except:
        data['parse_mode'] = None
        requests.post(url, data=data, timeout=30)
        return True

def main():
    global last_sent_link
    
    print(f"🤖 شروع - {datetime.now()}")
    print(f"بررسی r/{SUBREDDIT}")
    
    post = get_latest_normal_post()
    
    if not post:
        print("هیچ پست معمولی (غیر پین شده‌ای) یافت نشد")
        for chat_id in CHAT_IDS:
            send_notification(chat_id, "📭 **هیچ پست جدیدی منتشر نشده است.**")
        return
    
    # چک کردن تکراری (بر اساس لینک)
    if post['link'] == last_sent_link:
        print("این پست قبلاً فرستاده شده بود")
        for chat_id in CHAT_IDS:
            send_notification(chat_id, "📭 **هیچ پست جدیدی منتشر نشده است.**")
        return
    
    print(f"آخرین پست معمولی: {post['title'][:40]}...")
    
    for chat_id in CHAT_IDS:
        send_to_user(
            chat_id,
            translate_text(post['title']),
            translate_text(post['summary']) if post['summary'] else "",
            post['link'],
            post['image_url']
        )
        print(f"✓ ارسال شد به {chat_id}")
        time.sleep(1)
    
    last_sent_link = post['link']
    print("پایان")

if __name__ == "__main__":
    main()

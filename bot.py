import os
import feedparser
import requests
import time
import re
import json
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
SENT_POSTS_FILE = "sent_posts.json"

def load_sent_posts():
    """بارگذاری لیست پست‌های ارسال شده"""
    if os.path.exists(SENT_POSTS_FILE):
        try:
            with open(SENT_POSTS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_sent_posts(sent_posts):
    """ذخیره لیست پست‌های ارسال شده"""
    with open(SENT_POSTS_FILE, 'w') as f:
        json.dump(sent_posts, f)

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

def get_new_posts():
    url = f"https://www.reddit.com/r/{SUBREDDIT}/.rss"
    feed = feedparser.parse(url)
    sent_posts = load_sent_posts()
    new_posts = []
    
    for entry in feed.entries[:10]:
        post_link = entry.link
        # اگه این لینک قبلاً فرستاده نشده بود
        if post_link not in sent_posts:
            new_posts.append({
                'id': entry.id,
                'title': entry.title,
                'link': post_link,
                'summary': entry.summary,
                'image_url': extract_image_url(entry)
            })
    
    return new_posts, sent_posts

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
    print(f"🤖 شروع - {datetime.now()}")
    print(f"بررسی r/{SUBREDDIT}")
    
    posts, sent_posts = get_new_posts()
    print(f"پست‌های جدید: {len(posts)}")
    
    if not posts:
        print("پست جدیدی نیست")
        for chat_id in CHAT_IDS:
            send_notification(chat_id, "📭 **هیچ پست جدیدی منتشر نشده است.**")
        return
    
    # ارسال پست‌های جدید
    for post in posts:
        print(f"ترجمه: {post['title'][:40]}...")
        title_fa = translate_text(post['title'])
        summary_fa = translate_text(post['summary']) if post['summary'] else ""
        
        if title_fa:
            for chat_id in CHAT_IDS:
                send_to_user(chat_id, title_fa, summary_fa, post['link'], post['image_url'])
                print(f"✓ ارسال شد به {chat_id}")
                time.sleep(1)
            
            # ذخیره لینک به عنوان ارسال شده
            sent_posts[post['link']] = datetime.now().isoformat()
            save_sent_posts(sent_posts)
        time.sleep(2)
    
    print("پایان")

if __name__ == "__main__":
    main()

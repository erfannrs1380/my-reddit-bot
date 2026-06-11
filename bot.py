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

# لیست دو تا CHAT_ID (با کاما جدا کن)
CHAT_IDS = [
    8956194322,    # اکانت اول (خودت)
    1386381987     # اکانت دوم (دوستت)
]

translator = GoogleTranslator(source='auto', target='fa')

def clean_html(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text()
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'submitted by\s+/\w+', '', text)
    text = re.sub(r'/u/\w+', '', text)
    text = re.sub(r'u/\w+', '', text)
    text = text.strip()
    return text

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
    posts = []
    for entry in feed.entries[:10]:
        posts.append({
            'title': entry.title,
            'link': entry.link,
            'summary': entry.summary
        })
    return posts

def send_to_telegram(chat_id, title, summary, link):
    message = f"📝 {title}\n\n{summary}\n\n{link}"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message,
        'disable_web_page_preview': True
    }
    try:
        requests.post(url, data=data, timeout=30)
        return True
    except:
        return False

def main():
    print(f"🤖 شروع - {datetime.now()}")
    posts = get_new_posts()
    print(f"{len(posts)} پست پیدا شد")
    
    for post in posts:
        print(f"ترجمه: {post['title'][:40]}...")
        title_fa = translate_text(post['title'])
        summary_fa = translate_text(post['summary'])
        
        # ارسال برای هر دو اکانت
        for chat_id in CHAT_IDS:
            send_to_telegram(chat_id, title_fa, summary_fa, post['link'])
            print(f"✓ ارسال شد به {chat_id}")
            time.sleep(1)
        
        time.sleep(2)
    
    print("پایان")

if __name__ == "__main__":
    main()

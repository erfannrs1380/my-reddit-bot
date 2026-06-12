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

# خط درخواستی شما + fallback
CHAT_IDS = [x.strip() for x in os.environ.get("CHAT_IDS", "8956194322,1386381987").split(",") if x.strip()]

translator = GoogleTranslator(source='auto', target='fa')
LAST_POSTS_FILE = "last_posts.txt"

def get_last_post_ids():
    if os.path.exists(LAST_POSTS_FILE):
        with open(LAST_POSTS_FILE, 'r') as f:
            return {line.strip() for line in f if line.strip()}
    return set()

def save_post_ids(new_ids):
    if not new_ids:
        return
    with open(LAST_POSTS_FILE, 'a') as f:
        for pid in new_ids:
            f.write(f"{pid}\n")
    print(f"💾 {len(new_ids)} پست جدید ذخیره شد")

def clean_html(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text()
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'submitted by\s+/?u?/\w+', '', text, flags=re.I)
    text = re.sub(r'/?u/\w+', '', text, flags=re.I)
    text = re.sub(r'\|\s*\d+\s*votes?', '', text, flags=re.I)
    text = re.sub(r'\d+\s*comments?', '', text, flags=re.I)
    return text.strip()

def extract_image_url(entry):
    if hasattr(entry, 'summary'):
        soup = BeautifulSoup(entry.summary, 'html.parser')
        img = soup.find('img')
        if img and img.get('src'):
            return img['src']
    
    if hasattr(entry, 'links'):
        for link in entry.links:
            href = link.get('href', '').lower()
            if any(ext in href for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                return link.get('href')
    
    if hasattr(entry, 'summary'):
        urls = re.findall(r'https?://[^\s]+?\.(?:jpg|jpeg|png|gif|webp)', entry.summary, re.I)
        if urls:
            return urls[0]
    return None

def translate_text(text):
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
    link_text = f"[(لینک)]({link})"
    
    message = f"📝 {title}\n\n"
    if summary and len(summary) > 5:
        message += f"{summary}\n\n"
    message += link_text

    # ارسال عکس
    if image_url:
        try:
            photo_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            data = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': message,
                'parse_mode': 'Markdown'
            }
            response = requests.post(photo_url, data=data, timeout=30)
            if response.ok:
                return True
        except:
            pass

    # ارسال متن
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        requests.post(url, data=data, timeout=30)
        return True
    except Exception as e:
        print(f"❌ خطا در ارسال به {chat_id}: {e}")
        # تلاش مجدد بدون Markdown
        try:
            data['parse_mode'] = None
            requests.post(url, data=data, timeout=30)
            return True
        except:
            return False

def get_new_posts():
    url = f"https://www.reddit.com/r/{SUBREDDIT}/.rss"
    feed = feedparser.parse(url)
    last_ids = get_last_post_ids()
    new_posts = []
    
    for entry in feed.entries[:20]:
        if entry.id not in last_ids:
            new_posts.append({
                'id': entry.id,
                'title': entry.title,
                'link': entry.link,
                'summary': entry.get('summary', ''),
                'image_url': extract_image_url(entry)
            })
    return new_posts

def main():
    print(f"🤖 شروع ربات Reddit به تلگرام - {datetime.now()}")
    print(f"ساب‌ردیت: r/{SUBREDDIT}")
    print(f"چت آیدی‌ها: {CHAT_IDS}")
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نشده است!")
        return

    posts = get_new_posts()
    print(f"📊 {len(posts)} پست جدید پیدا شد")
    
    if not posts:
        print("✅ پست جدیدی وجود ندارد")
        return

    new_ids = []
    for post in posts:
        print(f"🔄 پردازش: {post['title'][:70]}...")
        
        title_fa = translate_text(post['title'])
        summary_fa = translate_text(post['summary']) if post.get('summary') else ""
        
        if not title_fa:
            continue
            
        success_count = 0
        for chat_id in CHAT_IDS:
            if send_to_user(chat_id, title_fa, summary_fa, post['link'], post['image_url']):
                print(f"   ✅ ارسال شد به {chat_id}")
                success_count += 1
            time.sleep(1.5)
        
        if success_count > 0:
            new_ids.append(post['id'])
        time.sleep(2)

    save_post_ids(new_ids)
    print("🎉 اجرای ربات با موفقیت تمام شد")

if __name__ == "__main__":
    main()

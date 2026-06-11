import os
import feedparser
import requests
import time
import re
import base64
from datetime import datetime
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

SUBREDDIT = os.environ.get("SUBREDDIT", "SquaredCircle")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GH_TOKEN = os.environ.get("GH_TOKEN")  # توکن گیت‌هاب

CHAT_IDS = [
    8956194322,
    1386381987
]

REPO_OWNER = "erfannrs1380"
REPO_NAME = "my-reddit-bot"
FILE_PATH = "last_post_link.txt"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

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

def read_last_link_from_github():
    try:
        headers = {"Authorization": f"token {GH_TOKEN}"}
        response = requests.get(API_URL, headers=headers)
        if response.status_code == 200:
            content = base64.b64decode(response.json()['content']).decode('utf-8')
            return content.strip()
        elif response.status_code == 404:
            return None
        else:
            print(f"خطا در خواندن فایل از گیت‌هاب: {response.status_code}")
            return None
    except Exception as e:
        print(f"خطا در read: {e}")
        return None

def save_last_link_to_github(link):
    try:
        headers = {"Authorization": f"token {GH_TOKEN}"}
        # اول فایل رو بگیریم تا sha داشته باشیم برای آپدیت
        response = requests.get(API_URL, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json()['sha']
        
        content_base64 = base64.b64encode(link.encode('utf-8')).decode('utf-8')
        data = {
            "message": f"update last post link: {datetime.now()}",
            "content": content_base64,
            "branch": "main"
        }
        if sha:
            data["sha"] = sha
        
        put_response = requests.put(API_URL, headers=headers, json=data)
        if put_response.status_code in [200, 201]:
            print("لینک آخرین پست با موفقیت در گیت‌هاب ذخیره شد")
        else:
            print(f"خطا در ذخیره لینک در گیت‌هاب: {put_response.status_code}")
    except Exception as e:
        print(f"خطا در save: {e}")

def get_latest_non_sticky_post():
    url = f"https://www.reddit.com/r/{SUBREDDIT}/.rss"
    feed = feedparser.parse(url)
    
    if not feed.entries:
        return None
    
    # رد کردن پست‌هایی که به نظر پین شده می‌رسند
    for entry in feed.entries[:15]:
        # پست پین شده معمولاً توی عنوانش [Pinned] داره یا خیلی قدیمیه
        title_lower = entry.title.lower()
        if 'pinned' in title_lower or 'wreddit\'s daily' in title_lower or 'discussion thread' in title_lower:
            print(f"⏭️ رد شد (احتمالاً پین شده): {entry.title[:40]}...")
            continue
        
        # اگه تاریخ پست خیلی قدیمی‌تر از امروز باشه، ردش کن
        if hasattr(entry, 'published_parsed'):
            pub_date = datetime(*entry.published_parsed[:6])
            now = datetime.now()
            diff_days = (now - pub_date).days
            if diff_days > 7:  # پست‌های بیشتر از ۷ روز رو رد کن
                print(f"⏭️ رد شد (قدیمی): {entry.title[:40]}...")
                continue
        
        return {
            'title': entry.title,
            'link': entry.link,
            'summary': entry.summary,
            'image_url': extract_image_url(entry)
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
    print(f"🤖 شروع - {datetime.now()}")
    print(f"بررسی r/{SUBREDDIT}")
    
    # ۱. آخرین پست معمولی رو بگیر
    post = get_latest_non_sticky_post()
    if not post:
        print("هیچ پست معمولی‌ای پیدا نشد")
        for chat_id in CHAT_IDS:
            send_notification(chat_id, "📭 **هیچ پست جدیدی منتشر نشده است.**")
        return
    
    # ۲. لینک آخرین پست قبلی رو از گیت‌هاب بخون
    last_link = read_last_link_from_github()
    if last_link == post['link']:
        print("همین پست قبلاً فرستاده شده بود")
        for chat_id in CHAT_IDS:
            send_notification(chat_id, "📭 **هیچ پست جدیدی منتشر نشده است.**")
        return
    
    # ۳. پست رو بفرست
    print(f"پست جدید: {post['title'][:40]}...")
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
    
    # ۴. لینک جدید رو توی گیت‌هاب ذخیره کن
    save_last_link_to_github(post['link'])
    print("پایان")

if __name__ == "__main__":
    main()

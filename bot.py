import os
import feedparser
import requests
import time
import re
import json
from datetime import datetime
from deep_translator import GoogleTranslator
from bs4 import BeautifulSoup

# تنظیمات
SUBREDDIT = os.environ.get("SUBREDDIT", "SquaredCircle")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
USERS_FILE = "users.json"
LAST_POSTS_FILE = "last_posts.txt"

# مترجم
translator = GoogleTranslator(source='auto', target='fa')

# ========== مدیریت کاربران ==========
def load_users():
    """بارگذاری لیست کاربران از فایل"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_users(users):
    """ذخیره لیست کاربران در فایل"""
    with open(USERS_FILE, 'w') as f:
        json.dump(list(users), f)

def add_user(chat_id):
    """اضافه کردن کاربر جدید"""
    users = load_users()
    if chat_id not in users:
        users.add(chat_id)
        save_users(users)
        print(f"کاربر جدید اضافه شد: {chat_id}")
        return True
    return False

# ========== مدیریت پیام‌های دریافتی ==========
def handle_updates():
    """بررسی پیام‌های جدید تلگرام و پردازش /start"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        response = requests.get(url, timeout=30)
        if response.ok:
            data = response.json()
            if data.get('ok') and data.get('result'):
                for update in data['result']:
                    if 'message' in update:
                        chat_id = update['message']['chat']['id']
                        text = update['message'].get('text', '')
                        
                        if text == '/start':
                            if add_user(chat_id):
                                send_message(chat_id, "✅ شما با موفقیت به ربات متصل شدید!\n\nهر ۲ ساعت یکبار جدیدترین پست‌ها براتون ارسال می‌شه.")
                        
                        # حذف این آپدیت از صف
                        update_id = update['update_id']
                        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={update_id+1}")
    except Exception as e:
        print(f"خطا در دریافت پیام‌ها: {e}")

def send_message(chat_id, text):
    """ارسال پیام به یک کاربر خاص"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'disable_web_page_preview': True
    }
    try:
        requests.post(url, data=data, timeout=30)
    except:
        pass

# ========== مدیریت پست‌های ارسال شده ==========
def get_last_post_ids():
    if os.path.exists(LAST_POSTS_FILE):
        with open(LAST_POSTS_FILE, 'r') as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_post_id(post_id):
    with open(LAST_POSTS_FILE, 'a') as f:
        f.write(f"{post_id}\n")

# ========== پاک کردن HTML و اسم کاربری ==========
def clean_html(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, 'html.parser')
    text = soup.get_text()
    text = re.sub(r'&#\d+;', '', text)
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    
    # حذف اسم کاربری به روش‌های مختلف
    text = re.sub(r'submitted by\s+/\w+', '', text)
    text = re.sub(r'Posted by\s+\w+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'/u/\w+', '', text)
    text = re.sub(r'u/\w+', '', text)
    text = re.sub(r'by\s+\w+', '', text)
    text = re.sub(r'\|\s*\d+\s*votes?\s*', '', text)
    text = re.sub(r'\d+\s*comments?', '', text)
    text = re.sub(r'From the \w+ community on Reddit:', '', text)
    text = re.sub(r'\[link\]\s*\[comments\]', '', text)
    
    text = text.strip()
    return text

# ========== پیدا کردن عکس (نسخه قوی) ==========
def extract_image_url(entry):
    """پیدا کردن آدرس عکس از پست ردیت"""
    # روش 1: توی خلاصه پست دنبال img بگرد
    if hasattr(entry, 'summary'):
        soup = BeautifulSoup(entry.summary, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return img_tag['src']
    
    # روش 2: توی لینک‌های پست دنبال عکس بگرد
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.get('type') and 'image' in link['type']:
                return link.get('href')
            if link.get('href'):
                href = link['href'].lower()
                if any(ext in href for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    return link['href']
    
    # روش 3: کل متن رو برای آدرس عکس بگرد
    if hasattr(entry, 'summary'):
        urls = re.findall(r'(https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp))', entry.summary, re.IGNORECASE)
        if urls:
            return urls[0]
    
    return None

# ========== ترجمه متن ==========
def translate_text(text):
    try:
        text = clean_html(text)
        if not text or len(text) < 5:
            return ""
        if len(text) > 1500:
            text = text[:1500] + "..."
        return translator.translate(text)
    except Exception as e:
        print(f"خطا در ترجمه: {e}")
        return text

# ========== دریافت پست‌های جدید از ردیت ==========
def get_new_posts():
    url = f"https://www.reddit.com/r/{SUBREDDIT}/.rss"
    feed = feedparser.parse(url)
    
    last_ids = get_last_post_ids()
    new_posts = []
    
    for entry in feed.entries[:10]:
        if entry.id not in last_ids:
            image_url = extract_image_url(entry)
            if image_url:
                print(f"✓ عکس پیدا شد: {entry.title[:30]}...")
            else:
                print(f"✗ عکس پیدا نشد: {entry.title[:30]}...")
            
            new_posts.append({
                'id': entry.id,
                'title': entry.title,
                'link': entry.link,
                'summary': entry.summary,
                'image_url': image_url
            })
    return new_posts

# ========== ارسال پست به یک کاربر ==========
def send_to_user(chat_id, title, summary, link, image_url=None):
    """ارسال پست (متن + عکس) به کاربر"""
    
    # ساخت پیام متنی
    message_parts = [f"📝 {title}"]
    if summary and len(summary) > 5:
        message_parts.append("")
        message_parts.append(summary)
    message_parts.append("")
    message_parts.append(f"🔗 [لینک در ردیت]({link})")
    
    message = "\n".join(message_parts)
    
    # ارسال عکس (اگر داشته باشد)
    if image_url:
        photo_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        photo_data = {
            'chat_id': chat_id,
            'photo': image_url
        }
        try:
            response = requests.post(photo_url, data=photo_data, timeout=30)
            if not response.ok:
                print(f"خطا در ارسال عکس: {response.text}")
            else:
                print("✓ عکس ارسال شد")
        except Exception as e:
            print(f"خطا در ارسال عکس: {e}")
    
    # ارسال متن
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    
    try:
        response = requests.post(url, data=data, timeout=30)
        return response.ok
    except:
        # اگر Markdown مشکل داشت، بدون فرمت بفرست
        data['parse_mode'] = None
        try:
            response = requests.post(url, data=data, timeout=30)
            return response.ok
        except Exception as e:
            print(f"خطا در ارسال متن: {e}")
            return False

# ========== تابع اصلی ==========
def main():
    print(f"🤖 ربات در حال اجرا - {datetime.now()}")
    
    # مرحله 1: بررسی کاربران جدید
    print("بررسی پیام‌های جدید تلگرام...")
    handle_updates()
    
    # مرحله 2: دریافت پست‌های جدید
    print(f"در حال بررسی سابردیت r/{SUBREDDIT}")
    posts = get_new_posts()
    print(f"پست‌های جدید: {len(posts)}")
    
    if not posts:
        print("هیچ پست جدیدی یافت نشد")
        return
    
    # مرحله 3: بارگذاری لیست کاربران
    users = load_users()
    print(f"تعداد کاربران فعال: {len(users)}")
    
    if not users:
        print("هیچ کاربری ثبت نشده است")
        return
    
    # مرحله 4: ارسال پست برای همه کاربران
    for post in posts:
        print(f"ترجمه: {post['title'][:40]}...")
        title_fa = translate_text(post['title'])
        summary_fa = translate_text(post['summary']) if post['summary'] else ""
        
        if title_fa:
            for user_id in users:
                send_to_user(user_id, title_fa, summary_fa, post['link'], post['image_url'])
                time.sleep(0.5)
            save_post_id(post['id'])
            print(f"✓ پست برای {len(users)} کاربر ارسال شد")
        else:
            print(f"✗ ترجمه失敗")
        time.sleep(2)
    
    print("پایان")

if __name__ == "__main__":
    main()

import os
import feedparser
import requests
import time
from datetime import datetime
from deep_translator import GoogleTranslator

# ---------- تنظیمات ----------
SUBREDDIT = "SquaredCircle"
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
LAST_POSTS_FILE = "last_posts.txt"

# ---------- مترجم ----------
translator = GoogleTranslator(source='auto', target='fa')

def is_text_post(entry):
    return 'media_content' not in entry

def get_last_post_ids():
    if os.path.exists(LAST_POSTS_FILE):
        with open(LAST_POSTS_FILE, 'r') as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_post_id(post_id):
    with open(LAST_POSTS_FILE, 'a') as f:
        f.write(f"{post_id}\n")

def get_new_text_posts():
    url = f"https://www.reddit.com/r/{SUBREDDIT}/.rss"
    feed = feedparser.parse(url)
    
    last_ids = get_last_post_ids()
    new_posts = []
    
    for entry in feed.entries:
        if entry.id not in last_ids and is_text_post(entry):
            new_posts.append({
                'id': entry.id,
                'title': entry.title,
                'link': entry.link,
                'summary': entry.summary,
                'published': entry.published
            })
    return new_posts

def translate_text(text):
    try:
        import re
        clean_text = re.sub('<[^<]+?>', '', text)
        if len(clean_text) > 4000:
            clean_text = clean_text[:4000] + "..."
        return translator.translate(clean_text)
    except Exception as e:
        print(f"Error in translation: {e}")
        return text[:500]

def send_to_telegram(title, content, link):
    message = f"📝 **{title}**\n\n{content}\n\n🔗 [مشاهده در ردیت]({link})"
    
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
        print(f"Error sending to Telegram: {e}")
        return False

def main():
    print(f"🤖 Bot is running - {datetime.now()}")
    print(f"Checking subreddit r/{SUBREDDIT}")
    
    new_posts = get_new_text_posts()
    print(f"New text posts found: {len(new_posts)}")
    
    for post in new_posts:
        print(f"Processing: {post['title'][:50]}...")
        
        title_fa = translate_text(post['title'])
        content_fa = translate_text(post['summary'])
        
        if send_to_telegram(title_fa, content_fa, post['link']):
            print(f"✓ Sent: {title_fa[:50]}...")
            save_post_id(post['id'])
        else:
            print(f"✗ Failed: {post['title'][:50]}...")
        
        time.sleep(3)
    
    print("Done")

if __name__ == "__main__":
    main()
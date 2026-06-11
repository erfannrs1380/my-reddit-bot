import os
import feedparser
import requests
import time
from datetime import datetime

# تنظیمات
SUBREDDIT = os.environ.get("SUBREDDIT", "AskReddit")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
LAST_POSTS_FILE = "last_posts.txt"

def get_last_post_ids():
    if os.path.exists(LAST_POSTS_FILE):
        with open(LAST_POSTS_FILE, 'r') as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_post_id(post_id):
    with open(LAST_POSTS_FILE, 'a') as f:
        f.write(f"{post_id}\n")

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
    # حذف تگ‌های HTML از متن
    import re
    clean_summary = re.sub('<[^<]+?>', '', summary)
    if len(clean_summary) > 1000:
        clean_summary = clean_summary[:1000] + "..."
    
    message = f"📝 {title}\n\n{clean_summary}\n\n🔗 {link}"
    
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
        print(f"Error: {e}")
        return False

def main():
    print(f"🤖 Bot running - {datetime.now()}")
    print(f"Subreddit: r/{SUBREDDIT}")
    
    posts = get_new_posts()
    print(f"New posts found: {len(posts)}")
    
    for post in posts:
        print(f"Sending: {post['title'][:50]}...")
        if send_to_telegram(post['title'], post['summary'], post['link']):
            print("✓ Sent")
            save_post_id(post['id'])
        else:
            print("✗ Failed")
        time.sleep(2)
    
    print("Done")

if __name__ == "__main__":
    main()

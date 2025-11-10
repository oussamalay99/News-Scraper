import asyncio
from datetime import datetime
from dotenv import load_dotenv
import os
import praw
from typing import Literal

from backend.db.mongo import close_db, connect_db, get_last_timestamp, save_post, drop_collections, update_last_timestamp
load_dotenv()
# client_id=os.getenv("CLIENT_ID", "")
# client_secret=os.getenv("CLIENT_SECRET", "")
# user_agent=os.getenv("USER_AGENT", "")


class Scraper(object):
    def __init__(self):
        self.TARGET_SUBS = os.getenv(
            "TARGET_SUBS", 'Futurology+worldnews+technology+MachineLearning+artificial').split("+")
        self.KEYWORDS = os.getenv(
            "KEYWORDS", 'ai+artificial intelligence+gpt+openai+automation+machine learning+deep learning').split("+")

    def text_contains_ai(self, text: str) -> bool:
        if not text:
            return False
        t = text.lower()
        return any(kw in t for kw in self.KEYWORDS)


class RedditScraper(Scraper):
    def __init__(self):
        super().__init__()
        self.client_id = os.getenv("CLIENT_ID", "")
        self.client_secret = os.getenv("CLIENT_SECRET", "")
        self.user_agent = os.getenv("USER_AGENT", "")
        self.praw = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent
        )
        self.reddit_fields = [
            "id", "title", "author", "subreddit", "score", "upvote_ratio",
            "num_comments", "created_utc", "url", "permalink", "selftext"
        ]

    def post_mentions_ai(self, post: praw.reddit.Submission) -> bool:
        return self.text_contains_ai(post.title or "") or self.text_contains_ai(getattr(post, "selftext", "") or "")

    def extract_post_data(self, post: praw.reddit.Submission) -> dict:
        data = {}
        for field in self.reddit_fields:
            value = getattr(post, field, None)

            if field == "author":
                value = value.name if value else "unknown"
            elif field == "subreddit":
                value = value.display_name if value else "unknown"
            elif field == "created_utc":
                value = datetime.fromtimestamp(
                    post.created_utc) if value else datetime.now()
            data[field] = value

        if "permalink" in data and data["permalink"]:
            data["permalink"] = f"https://reddit.com{data['permalink']}"

        return data

    def scrape(self, type: Literal["top", "hot", "new", "rising"] = "new", limit: int = 25, incremental: bool = True):
        for sub in self.TARGET_SUBS:
            subreddit = self.praw.subreddit(sub)
            last_created_utc = get_last_timestamp(sub)
            new_last_created_utc = last_created_utc
            
            if type == "top":
                posts = subreddit.top(limit=limit)
            elif type == "hot":
                posts = subreddit.hot(limit=limit)
            elif type == "new":
                posts = subreddit.new(limit=limit)
            elif type == "rising":
                posts = subreddit.rising(limit=limit)
            else:
                raise ValueError(f"Unsupported Scraping Type: {type}")
            new_posts_count = 0
            for post in posts:
                
                if incremental and post.created_utc <= last_created_utc:
                    continue
                
                if self.post_mentions_ai(post):
                    doc = self.extract_post_data(post)
                    save_post(doc)
                    new_posts_count += 1
                    print(f"✅ Saved post: {post.title[:60]}")

                    if post.created_utc > new_last_created_utc:
                        new_last_created_utc = post.created_utc

            if incremental:
                update_last_timestamp(sub, new_last_created_utc)
                print(f"📅 Updated timestamp for r/{sub}: {new_last_created_utc}")
            print(f"📈 Finished r/{sub}: {new_posts_count} posts saved.")


class NewsApiScrapper(object):
    def __init__(self):
        pass

# subreddits = ["news", "worldnews", "politics", "technolgy", "economics"]


# reddit = praw.Reddit(
#     client_id=client_id,
#     client_secret=client_secret,
#     user_agent=user_agent
# )
# print(reddit.read_only)
# subreddit = reddit.subreddit("news")
# for post in subreddit.new(limit=5):
#     print(post.keys())
def main():
    connect_db()
    # drop_collections()
    scraper = RedditScraper()
    scraper.scrape(limit=500)
    
    close_db()


if __name__ == "__main__":
    main()

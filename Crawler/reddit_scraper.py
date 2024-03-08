from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime


class RedditScraper():
  def __init__(self, posts_collection, subreddit_posts_collection):
    self.load_timeout = 10

    self.posts_collection = posts_collection
    self.subreddit_posts_collection = subreddit_posts_collection

    self._driver = None

  def open(self):
    self._driver = webdriver.Chrome()
    self._driver.maximize_window()

  def close(self):
     self._driver.close()

  def get_posts(self, initial_posts_length):
    attempts_to_load = 0

    while True:
        try:
            # Wait for the number of posts to increase
            WebDriverWait(self._driver, self.load_timeout).until(
                lambda d: len(d.find_elements(By.XPATH, "//article")) > initial_posts_length
            )

            # Get all articles on the page
            articles = WebDriverWait(self._driver, self.load_timeout).until(
                EC.presence_of_all_elements_located((By.XPATH, f"//article"))
            )
            
            return articles
        except TimeoutException:
            if attempts_to_load > 3:
              return []
            else:
              attempts_to_load += 1
    
  
  def load_posts(self, article):
    attempts_to_load = 0
    initial_scroll_position = self._driver.execute_script("return window.pageYOffset;")

    while True:
        try:
          # Scroll into post's article view
          self._driver.execute_script("arguments[0].scrollIntoView();", article)

          # Make sure the page has been fully loaded
          WebDriverWait(self._driver, self.load_timeout).until(
              EC.invisibility_of_element_located((By.XPATH, f"//faceplate-partial[@loading='programmatic' and @hasbeenloaded='true']"))
          )

          new_scroll_position = self._driver.execute_script("return window.pageYOffset;")

          if new_scroll_position > initial_scroll_position or attempts_to_load > 3:
             break
          else:
             attempts_to_load += 1

        except TimeoutException:
            if attempts_to_load > 3:
                raise Exception("Time out for waiting posts to load.")
            else:
                attempts_to_load += 1
    
  def is_pinned_post(self, article):
    try:
        article.find_element(By.CSS_SELECTOR, f"shreddit-status-icons svg.hidden.stickied-status")

        return False
    except NoSuchElementException:
        return True

 
  def retreive_post(self, article):
      attempts_to_load = 0

      while True:
          try:
              post_id = article.find_element(By.XPATH, "./shreddit-post").get_attribute("id").split('_')[-1]
              title = article.get_attribute("aria-label")
              content = article.find_element(By.XPATH, ".//a[@slot='text-body']").text
              number_of_comments = article.find_element(By.XPATH, "./shreddit-post").get_attribute("comment-count")
              rating = article.find_element(By.XPATH, "./shreddit-post").get_attribute("score")
              
              return post_id, {"post_id": post_id, "title": title, "content": content, "number_of_comments": number_of_comments, "rating": rating}
          except StaleElementReferenceException:
              if attempts_to_load > 3:
                raise Exception("Time out for post data retreival.")
              else:
                attempts_to_load += 1

  def retreive_posts(self, number_of_posts):
    posts = self.get_posts(0)
    post_index = 0
    post_ids = []
    
    while posts and number_of_posts != len(post_ids):
        is_pinned = self.is_pinned_post(posts[post_index])
        
        if not is_pinned:
            post_id, post = self.retreive_post(posts[post_index])
            
            self.posts_collection.update_one({"post_id": post_id},{ "$set": { "updated_at": datetime.utcnow(), **post}}, upsert=True)
            post_ids.append(post_id)
        
        post_index += 1

        if len(posts) == post_index:
          self.load_posts(posts[post_index - 1])
          posts = self.get_posts(len(posts))

    return post_ids
  
  def retreive_subreddit_posts(self, subreddit):
    self._driver.get(f"https://www.reddit.com/r/{subreddit}/")
    
    post_ids = self.retreive_posts(100)
   
    self.subreddit_posts_collection.update_one({"subreddit": subreddit}, {"$set": {"updated_at": datetime.utcnow(), "post_ids": post_ids}}, upsert=True)
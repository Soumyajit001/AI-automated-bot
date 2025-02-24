from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time
import pandas as pd
import re
import logging
import random
from webdriver_manager.chrome import ChromeDriverManager
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EnhancedInstagramFinder:
    def __init__(self, username, password, headless=False):
        self.username = username
        self.password = password

        # Configure Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--lang=en-US")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")

        # Add experimental flags to handle cookie consent popups
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.images": 1
        })

        # Initialize the Chrome driver
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 15)
        self.short_wait = WebDriverWait(self.driver, 5)
        self.creators_data = []

    def login(self):
        """Login to Instagram with improved error handling"""
        try:
            logger.info("Logging in to Instagram...")
            self.driver.get("https://www.instagram.com/")
            time.sleep(3)  # Wait for initial page load

            # Handle cookie consent if it appears
            try:
                cookie_buttons = self.short_wait.until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Allow')]"))
                )
                for button in cookie_buttons:
                    if button.is_displayed():
                        button.click()
                        logger.info("Accepted cookies")
                        time.sleep(1)
                        break
            except TimeoutException:
                logger.info("No cookie consent dialog found")

            # Wait for the login page to load and enter credentials
            username_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username']")))
            password_input = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password']")))

            # Clear and enter credentials with human-like typing
            username_input.clear()
            self._type_like_human(username_input, self.username)
            password_input.clear()
            self._type_like_human(password_input, self.password)

            # Click login button
            login_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
            login_button.click()

            # Wait for login to complete
            time.sleep(5)

            # Handle "Save Your Login Info?" dialog - multiple possible texts
            self._dismiss_dialog_if_present([
                "//button[contains(text(), 'Not Now')]",
                "//button[contains(text(), 'Not now')]",
                "//button[contains(text(), 'Skip')]",
                "//button[contains(text(), 'Cancel')]"
            ], "Save login info prompt")

            # Handle notifications dialog
            self._dismiss_dialog_if_present([
                "//button[contains(text(), 'Not Now')]",
                "//button[contains(text(), 'Not now')]",
                "//button[contains(text(), 'Cancel')]"
            ], "Notifications prompt")

            # Verify login success
            try:
                self.short_wait.until(EC.presence_of_element_located((By.XPATH,
                                                                      "//div[@class='x9f619 xjbqb8w x78zum5 x168nmei x13lgxp2 x5pf9jr xo71vjh x1uhb9sk x1plvlek xryxfnj x1c4vz4f x2lah0s xdt5ytf xqjyukv x1qjc9v5 x1oa3qoh x1nhvcw1']")))
                logger.info("Successfully logged into Instagram")
                return True
            except TimeoutException:
                logger.error("Login verification failed - could not find home feed")
                return False

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            # Take screenshot of login failure
            self.driver.save_screenshot("login_error.png")
            logger.info("Screenshot saved as login_error.png")
            return False

    def _type_like_human(self, element, text):
        """Type text with random delays between keystrokes to simulate human typing"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))

    def _dismiss_dialog_if_present(self, xpath_list, dialog_name):
        """Try multiple XPaths to dismiss a dialog that might appear"""
        for xpath in xpath_list:
            try:
                button = self.short_wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                button.click()
                logger.info(f"Dismissed {dialog_name}")
                time.sleep(2)
                return True
            except TimeoutException:
                continue
        logger.info(f"No {dialog_name} appeared")
        return False

    def _retry_stale_element(self, find_func, max_retries=3):
        """Retry function when StaleElementReferenceException occurs"""
        for attempt in range(max_retries):
            try:
                return find_func()
            except StaleElementReferenceException:
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)

    def explore_page(self):
        """Explore the Instagram explore page to find trending content"""
        try:
            logger.info("Navigating to explore page...")
            self.driver.get("https://www.instagram.com/explore/")
            time.sleep(5)

            # Scroll down to load more content
            self._scroll_page(5)

            # Get all post links
            posts = self.wait.until(EC.presence_of_all_elements_located(
                (By.XPATH, "//a[contains(@href, '/p/')]")))

            post_urls = []
            for post in posts[:30]:  # Get up to 30 posts
                try:
                    href = post.get_attribute('href')
                    if href and '/p/' in href and href not in post_urls:
                        post_urls.append(href)
                except Exception as e:
                    logger.error(f"Error getting post URL: {e}")

            logger.info(f"Found {len(post_urls)} posts on explore page")
            return post_urls
        except Exception as e:
            logger.error(f"Error exploring trending page: {str(e)}")
            return []

    def _scroll_page(self, num_scrolls):
        """Scroll the page to load more content"""
        for _ in range(num_scrolls):
            self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(random.uniform(1, 2))

    def search_hashtag(self, hashtag):
        """Search for posts by hashtag with improved reliability"""
        try:
            logger.info(f"Searching hashtag: #{hashtag}")
            self.driver.get(f"https://www.instagram.com/explore/tags/{hashtag}/")

            # Wait for page to load
            time.sleep(5)

            # Check if hashtag exists
            try:
                self.short_wait.until(
                    EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), 'This hashtag does not exist')]")))
                logger.warning(f"Hashtag #{hashtag} does not exist")
                return []
            except TimeoutException:
                pass  # Hashtag exists, continue

            # Wait for the posts to load and scroll to load more
            try:
                self.wait.until(EC.presence_of_element_located((By.XPATH, "//article//a[contains(@href, '/p/')]")))
                self._scroll_page(3)
            except TimeoutException:
                logger.warning(f"No posts found for hashtag #{hashtag}")
                return []

            # Get recent posts
            post_links = self.driver.find_elements(By.XPATH, "//article//a[contains(@href, '/p/')]")
            post_urls = []

            for link in post_links[:20]:  # Get first 20 posts
                try:
                    url = link.get_attribute('href')
                    if url and url not in post_urls:
                        post_urls.append(url)
                except Exception as e:
                    logger.error(f"Error getting post URL: {e}")

            logger.info(f"Found {len(post_urls)} posts for hashtag #{hashtag}")
            return post_urls
        except Exception as e:
            logger.error(f"Error searching hashtag: {str(e)}")
            return []

    def search_keyword(self, keyword):
        """Search Instagram for keywords/accounts"""
        try:
            logger.info(f"Searching keyword: {keyword}")
            self.driver.get("https://www.instagram.com/")
            time.sleep(3)

            # Click on search icon (magnifying glass)
            search_icon = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//span[contains(@aria-label, 'Search')]/..")))
            search_icon.click()
            time.sleep(2)

            # Type in search box
            search_input = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//input[@placeholder='Search']")))
            self._type_like_human(search_input, keyword)
            time.sleep(3)

            # Wait for search results and get accounts
            accounts = self.wait.until(EC.presence_of_all_elements_located(
                (By.XPATH, "//div[@role='none']//a[contains(@href, '/')]")))

            account_usernames = []
            for account in accounts[:10]:  # First 10 accounts
                try:
                    username = account.get_attribute('href').split('/')[-2]
                    if username and username not in account_usernames:
                        account_usernames.append(username)
                except Exception as e:
                    logger.error(f"Error getting account username: {e}")

            logger.info(f"Found {len(account_usernames)} accounts for keyword '{keyword}'")
            return account_usernames
        except Exception as e:
            logger.error(f"Error searching keyword: {str(e)}")
            return []

    def extract_post_data(self, post_url):
        """Extract engagement data from a post with improved metrics extraction"""
        try:
            logger.info(f"Analyzing post: {post_url}")
            self.driver.get(post_url)
            time.sleep(random.uniform(3, 5))

            # Extract username with better selector
            username_element = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@class, 'x1i10hfl') and not(contains(@href, 'tagged'))]")))
            username = username_element.get_attribute('href').split('/')[-2]

            # Check if it's a video by looking for view count
            is_video = False
            views = 0
            try:
                views_element = self.short_wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//span[contains(text(), 'views') or contains(text(), 'Views')]/..")))
                views_text = views_element.text
                # Extract numbers from text like "1,234,567 views"
                views = int(''.join(filter(str.isdigit, views_text)))
                is_video = True
                has_million_views = views >= 1000000
                logger.info(f"Post has {views} views")
            except TimeoutException:
                is_video = False
                has_million_views = False

            # Extract likes - try multiple possible selectors
            likes = 0
            like_selectors = [
                "//section//span/span[contains(@class, 'x193iq5w')]",
                "//section//a[contains(@href, 'liked_by')]/span",
                "//span[contains(@class, '_aap6')]",
                "//article//span[contains(@class, 'x193iq5w')]"
            ]

            for selector in like_selectors:
                try:
                    likes_element = self.driver.find_element(By.XPATH, selector)
                    likes_text = likes_element.text
                    likes = int(''.join(filter(str.isdigit, likes_text)))
                    logger.info(f"Post has {likes} likes")
                    break
                except (NoSuchElementException, ValueError):
                    continue

            # Extract comments count
            comments = 0
            try:
                comments_element = self.driver.find_element(
                    By.XPATH, "//span[contains(text(), 'comment') or contains(text(), 'Comment')]")
                comments_text = comments_element.text
                comments = int(''.join(filter(str.isdigit, comments_text)))
            except (NoSuchElementException, ValueError):
                # Try alternative method - count comment elements
                try:
                    comment_elements = self.driver.find_elements(By.XPATH, "//ul//li[contains(@class, 'gLFyf')]")
                    comments = len(comment_elements)
                except Exception:
                    pass

            # Get post timestamp
            timestamp = ""
            try:
                time_element = self.driver.find_element(By.XPATH, "//time")
                timestamp = time_element.get_attribute('datetime')
            except NoSuchElementException:
                pass

            # Try to extract caption
            caption = ""
            try:
                caption_element = self.driver.find_element(
                    By.XPATH, "//div[contains(@class, '_a9zs')]/span")
                caption = caption_element.text
            except NoSuchElementException:
                pass

            # Calculate engagement - if video use views, otherwise use estimated follower count
            engagement_denominator = views if is_video and views > 0 else 1
            engagement_rate = (likes + comments) / engagement_denominator * 100 if engagement_denominator > 1 else 0

            # Return comprehensive post data
            return {
                'username': username,
                'post_url': post_url,
                'is_video': is_video,
                'views': views,
                'likes': likes,
                'comments': comments,
                'has_million_views': has_million_views,
                'engagement_rate': engagement_rate,
                'timestamp': timestamp,
                'caption': caption
            }
        except Exception as e:
            logger.error(f"Error extracting post data: {str(e)}")
            return None

    def analyze_creator_profile(self, username):
        """Analyze a creator's profile with improved metrics collection"""
        try:
            logger.info(f"Analyzing profile: {username}")
            self.driver.get(f"https://www.instagram.com/{username}/")
            time.sleep(random.uniform(3, 5))

            # Check if account exists and is public
            try:
                self.short_wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//h2[contains(text(), 'Sorry, this page') or contains(text(), 'isn't available')]")))
                logger.warning(f"Account @{username} doesn't exist or is private")
                return None
            except TimeoutException:
                pass  # Account exists and is public

            # Extract account metrics
            metrics = {}

            # Get profile name
            try:
                name_element = self.driver.find_element(By.XPATH, "//h1")
                metrics['name'] = name_element.text
            except NoSuchElementException:
                metrics['name'] = username

            # Get bio
            try:
                bio_element = self.driver.find_element(
                    By.XPATH, "//div[contains(@class, '_aa_c')]")
                metrics['bio'] = bio_element.text
            except NoSuchElementException:
                metrics['bio'] = ""

            # Get follower count with multiple possible selectors
            followers = 0
            follower_selectors = [
                "//a[contains(@href, 'followers')]/span",
                "//a[contains(@href, 'followers')]//span[contains(@class, '_ac2a')]",
                "//div[contains(@class, '_aa_i')]//span",
                "//div[contains(@class, '_ab8w')]//span[contains(@class, '_ac2a')]"
            ]

            for selector in follower_selectors:
                try:
                    followers_element = self.driver.find_element(By.XPATH, selector)
                    followers_text = followers_element.text
                    if 'k' in followers_text.lower():
                        followers = float(followers_text.lower().replace('k', '')) * 1000
                    elif 'm' in followers_text.lower():
                        followers = float(followers_text.lower().replace('m', '')) * 1000000
                    else:
                        followers = int(''.join(filter(str.isdigit, followers_text)))
                    metrics['followers'] = int(followers)
                    break
                except (NoSuchElementException, ValueError):
                    continue

            if 'followers' not in metrics:
                metrics['followers'] = 0
                logger.warning(f"Could not extract follower count for @{username}")

            # Check account type (creator/business account)
            try:
                category_element = self.driver.find_element(
                    By.XPATH, "//div[contains(@class, '_aa_c')]//div[contains(@class, '_ab8w')]")
                metrics['category'] = category_element.text
                metrics['is_creator_account'] = True
            except NoSuchElementException:
                metrics['category'] = ""
                metrics['is_creator_account'] = False

            # Get recent posts (works for both grid view and list view)
            post_urls = []
            try:
                post_elements = self.wait.until(EC.presence_of_all_elements_located(
                    (By.XPATH, "//article//a[contains(@href, '/p/')]")))

                for element in post_elements[:9]:  # Get the most recent 9 posts
                    try:
                        url = element.get_attribute('href')
                        if url and url not in post_urls:
                            post_urls.append(url)
                    except Exception as e:
                        logger.error(f"Error getting post URL: {e}")

                logger.info(f"Found {len(post_urls)} recent posts for @{username}")
            except TimeoutException:
                logger.warning(f"No posts found for @{username}")

            # Analyze recent posts to determine engagement trends
            post_data = []
            for url in post_urls[:5]:  # Analyze top 5 most recent posts
                data = self.extract_post_data(url)
                if data:
                    post_data.append(data)
                time.sleep(random.uniform(2, 4))

            # Calculate engagement metrics
            if post_data:
                # Overall engagement metrics
                video_posts = [p for p in post_data if p['is_video']]
                image_posts = [p for p in post_data if not p['is_video']]

                # Average engagement calculation
                total_eng_rates = sum(p['engagement_rate'] for p in post_data)
                avg_engagement_rate = total_eng_rates / len(post_data) if post_data else 0

                # Calculate if on a hot streak (most recent post exceeds avg by 15%+)
                most_recent_eng = post_data[0]['engagement_rate'] if post_data else 0
                on_hot_streak = most_recent_eng >= avg_engagement_rate * 1.15

                # Check for any viral content (1M+ views)
                has_viral_video = any(p['has_million_views'] for p in post_data)

                # Return comprehensive creator profile
                return {
                    'username': username,
                    'name': metrics.get('name', ''),
                    'bio': metrics.get('bio', ''),
                    'category': metrics.get('category', ''),
                    'is_creator_account': metrics.get('is_creator_account', False),
                    'followers': metrics.get('followers', 0),
                    'posts_analyzed': len(post_data),
                    'avg_engagement_rate': avg_engagement_rate,
                    'latest_post_engagement': most_recent_eng,
                    'on_hot_streak': on_hot_streak,
                    'has_viral_video': has_viral_video,
                    'video_post_count': len(video_posts),
                    'image_post_count': len(image_posts),
                    'recent_posts': post_data
                }
            else:
                logger.warning(f"Could not analyze any posts for @{username}")
                return {
                    'username': username,
                    'name': metrics.get('name', ''),
                    'bio': metrics.get('bio', ''),
                    'category': metrics.get('category', ''),
                    'is_creator_account': metrics.get('is_creator_account', False),
                    'followers': metrics.get('followers', 0),
                    'posts_analyzed': 0,
                    'avg_engagement_rate': 0,
                    'latest_post_engagement': 0,
                    'on_hot_streak': False,
                    'has_viral_video': False,
                    'video_post_count': 0,
                    'image_post_count': 0,
                    'recent_posts': []
                }
        except Exception as e:
            logger.error(f"Error analyzing profile: {str(e)}")
            self.driver.save_screenshot(f"profile_error_{username}.png")
            return None

    def find_suggested_accounts(self, seed_account):
        """Use Instagram's suggestion algorithm to find similar creators"""
        try:
            logger.info(f"Finding accounts similar to: {seed_account}")
            self.driver.get(f"https://www.instagram.com/{seed_account}/")
            time.sleep(3)

            # Click on followers to open the list
            followers_link = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@href, 'followers')]")))
            followers_link.click()
            time.sleep(3)

            # Get accounts from the followers list
            suggested_accounts = []
            try:
                account_elements = self.wait.until(EC.presence_of_all_elements_located(
                    (By.XPATH, "//div[@role='dialog']//a[contains(@class, 'notranslate')]")))

                for element in account_elements[:20]:  # Get up to 20 suggested accounts
                    try:
                        username = element.text
                        if username and username != seed_account and username not in suggested_accounts:
                            suggested_accounts.append(username)
                    except Exception as e:
                        logger.error(f"Error getting suggested account: {e}")

                logger.info(f"Found {len(suggested_accounts)} accounts similar to @{seed_account}")
            except TimeoutException:
                logger.warning(f"Could not find suggested accounts for @{seed_account}")

            # Close the dialog
            try:
                close_button = self.driver.find_element(By.XPATH,
                                                        "//div[@role='dialog']//button[contains(@aria-label, 'Close')]")
                close_button.click()
                time.sleep(1)
            except NoSuchElementException:
                pass

            return suggested_accounts
        except Exception as e:
            logger.error(f"Error finding suggested accounts: {str(e)}")
            return []

    def find_viral_creators(self, industry_tags=None, min_followers=1000, min_engagement=5.0):
        """Find creators with viral potential using multiple discovery methods"""
        if industry_tags is None:
            industry_tags = ["viral", "trending", "creator", "contentcreator"]

        all_creators = set()
        viral_creators = []

        # Method 1: Search popular hashtags in the industry
        logger.info("DISCOVERY METHOD 1: Hashtag search")
        for tag in industry_tags:
            posts = self.search_hashtag(tag)
            for post_url in posts:
                try:
                    post_data = self.extract_post_data(post_url)
                    if post_data and post_data['username'] not in all_creators:
                        all_creators.add(post_data['username'])
                        # Quick filter: only analyze profiles with high engagement or viral indicators
                        if post_data['has_million_views'] or post_data['engagement_rate'] > min_engagement:
                            logger.info(f"Found potential creator @{post_data['username']} from hashtag #{tag}")
                except Exception as e:
                    logger.error(f"Error processing post {post_url}: {str(e)}")
                time.sleep(random.uniform(1, 2))

        # Method 2: Explore page for trending content
        logger.info("DISCOVERY METHOD 2: Explore page")
        trending_posts = self.explore_page()
        for post_url in trending_posts:
            try:
                post_data = self.extract_post_data(post_url)
                if post_data and post_data['username'] not in all_creators:
                    all_creators.add(post_data['username'])
                    if post_data['has_million_views'] or post_data['engagement_rate'] > min_engagement:
                        logger.info(f"Found potential creator @{post_data['username']} from explore page")
            except Exception as e:
                logger.error(f"Error processing explore post {post_url}: {str(e)}")
            time.sleep(random.uniform(1, 2))

        # Method 3: Search for industry keywords to find creator accounts
        logger.info("DISCOVERY METHOD 3: Keyword search")
        keywords = ["content creator", "viral creator", "trending"]
        for keyword in keywords:
            accounts = self.search_keyword(keyword)
            for username in accounts:
                if username not in all_creators:
                    all_creators.add(username)
                    logger.info(f"Found potential creator @{username} from keyword '{keyword}'")
            time.sleep(random.uniform(2, 3))

        # Method 4: Use seed accounts to find similar creators
        logger.info("DISCOVERY METHOD 4: Similar account discovery")
        seed_accounts = list(all_creators)[:3] if all_creators else ["instagram"]
        for seed in seed_accounts:
            similar_accounts = self.find_suggested_accounts(seed)
            for username in similar_accounts:
                if username not in all_creators:
                    all_creators.add(username)
                    logger.info(f"Found potential creator @{username} similar to @{seed}")
            time.sleep(random.uniform(2, 3))

        # Analyze each discovered creator in depth
        logger.info(f"Found {len(all_creators)} potential creators. Analyzing profiles...")
        for username in all_creators:
            profile_data = self.analyze_creator_profile(username)

            if profile_data and profile_data['followers'] >= min_followers:
                # Check for viral indicators:
                # 1. Has a video with 1M+ views
                # 2. Currently on a hot streak (15%+ above average engagement)
                # 3. Consistently high engagement rate
                if (profile_data['has_viral_video'] or
                        profile_data['on_hot_streak'] or
                        profile_data['avg_engagement_rate'] > min_engagement):
                    viral_creators.append(profile_data)
                    logger.info(f"✅ Qualified viral creator: @{username}")
                    logger.info(f"   Followers: {profile_data['followers']:,}")
                    logger.info(f"   Viral video: {'Yes' if profile_data['has_viral_video'] else 'No'}")
                    logger.info(f"   Hot streak: {'Yes' if profile_data['on_hot_streak'] else 'No'}")
                    logger.info(f"   Avg engagement: {profile_data['avg_engagement_rate']:.2f}%")

            time.sleep(random.uniform(3, 5))

        self.creators_data = viral_creators
        logger.info(f"Found {len(viral_creators)} qualified viral creators")
        return viral_creators

    def send_message(self, username, message_template):
        """Send a DM to a creator with improved reliability"""
        try:
            logger.info(f"Attempting to message: {username}")
            self.driver.get(f"https://www.instagram.com/{username}/")
            time.sleep(random.uniform(2, 4))

            # Try multiple selectors for the message button
            message_selectors = [
                "//div[text()='Message']",
                "//button[contains(text(), 'Message')]",
                "//a[contains(@href, '/direct/')]"
            ]

            clicked = False
            for selector in message_selectors:
                try:
                    message_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    message_btn.click()
                    clicked = True
                    break
                except TimeoutException:
                    continue

            if not clicked:
                logger.error(f"Could not find message button for @{username}")
                return False

            time.sleep(random.uniform(2, 4))

            # Type message - try multiple selectors for the input field
            input_selectors = [
                "//textarea[@placeholder='Message...']",
                "//div[@role='textbox']",
                "//div[contains(@aria-label, 'Message')]"
            ]

            typed = False
            for selector in input_selectors:
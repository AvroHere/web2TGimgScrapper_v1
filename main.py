import os
import requests
import concurrent.futures
import urllib.parse
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from telegram import Update, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = "8142872572:AAGc5bMXlHuJW71VeSwWWRW2TKhg9a7nNDs"
MAX_IMAGES_PER_MESSAGE = 10  # Reduced from 20 to avoid rate limits
MAX_WORKERS = 10
TEMPORARY_FOLDER = "temp_images"
DELAY_BETWEEN_LINKS = 15

# Admin and group IDs
ADMIN_ID = 8139996030
GROUP_ID = -1002602630495
TARGET_GROUP = -1002602630495  # Using group ID instead of username for reliability

os.makedirs(TEMPORARY_FOLDER, exist_ok=True)

class ImageDownloaderBot:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.link_queue = []
        self.processing = False
        self.paused = False
        self.current_processing_msg = None
        self.over_mode = False
        self.saved_queue = []  # To store the original queue during /over mode
        self.processed_count = 0  # Counter for processed links

    def clean_temp_folder(self):
        """Remove all temporary downloaded images"""
        for filename in os.listdir(TEMPORARY_FOLDER):
            file_path = os.path.join(TEMPORARY_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Error deleting {file_path}: {e}")

    async def process_text_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process text file containing URLs"""
        file = await context.bot.get_file(update.message.document)
        file_path = os.path.join(TEMPORARY_FOLDER, "links.txt")
        await file.download_to_drive(file_path)
        
        with open(file_path, 'r') as f:
            urls = [line.strip() for line in f.readlines() if line.strip()]
        
        os.unlink(file_path)
        return urls

    def extract_image_links(self, url):
        """Extract direct image links from a webpage"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            image_links = set()
            
            for img_tag in soup.find_all('img'):
                if img_tag.get('src'):
                    absolute_url = urllib.parse.urljoin(url, img_tag['src'])
                    if any(ext in absolute_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        image_links.add(absolute_url)
                
                parent = img_tag.parent
                if parent and parent.name == 'a' and parent.get('href'):
                    absolute_url = urllib.parse.urljoin(url, parent['href'])
                    if any(ext in absolute_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        image_links.add(absolute_url)
            
            for a_tag in soup.find_all('a'):
                if a_tag.get('href'):
                    absolute_url = urllib.parse.urljoin(url, a_tag['href'])
                    if any(ext in absolute_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        image_links.add(absolute_url)
            
            return sorted(image_links)
        
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            return []

    async def download_all_images(self, image_links):
        """Download all images in parallel and return their paths"""
        self.clean_temp_folder()
        downloaded_files = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for idx, url in enumerate(image_links, 1):
                futures.append(executor.submit(self.download_image, url, idx))
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    downloaded_files.append(result)
        
        return downloaded_files

    def download_image(self, url, idx):
        """Download a single image and return its local path"""
        try:
            response = self.session.get(url, stream=True, timeout=15)
            response.raise_for_status()
            
            # Get content type to determine extension
            content_type = response.headers.get('content-type', '').lower()
            ext = '.jpg'  # default
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'png' in content_type:
                ext = '.png'
            elif 'gif' in content_type:
                ext = '.gif'
            elif 'webp' in content_type:
                ext = '.webp'
            
            # Create filename with proper extension
            filename = f"image_{idx}{ext}"
            file_path = os.path.join(TEMPORARY_FOLDER, filename)
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            
            logger.info(f"Downloaded: {filename}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None

    async def send_images_in_batches(self, context: ContextTypes.DEFAULT_TYPE, chat_id, image_paths):
        """Send images in batches and return success count"""
        success_count = 0
        total_images = len(image_paths)
        
        for i in range(0, total_images, MAX_IMAGES_PER_MESSAGE):
            while self.paused:
                await asyncio.sleep(1)
                if not self.processing:
                    return success_count
                    
            batch = image_paths[i:i + MAX_IMAGES_PER_MESSAGE]
            media_group = [InputMediaPhoto(media=open(file, 'rb')) for file in batch]
            
            try:
                await context.bot.send_media_group(
                    chat_id=chat_id,
                    media=media_group
                )
                success_count += len(batch)
                logger.info(f"Successfully sent batch of {len(batch)} images to chat {chat_id}")
            except Exception as e:
                logger.error(f"Error sending batch to chat {chat_id}: {e}")
                # Try sending images individually if batch fails
                for file in batch:
                    try:
                        with open(file, 'rb') as photo:
                            await context.bot.send_photo(
                                chat_id=chat_id,
                                photo=photo
                            )
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send individual image to chat {chat_id}: {e}")
        
        return success_count

    async def process_single_link(self, context: ContextTypes.DEFAULT_TYPE, url, chat_id, is_group):
        """Process a single URL: download all images and send them"""
        try:
            image_links = self.extract_image_links(url)
            if not image_links:
                return False, "❌ No images found"
            
            # Update status with found image count
            status_msg = f"🔍 Processing: {url}\n📷 Found {len(image_links)} images\n📊 Remaining links: {len(self.link_queue)}"
            if is_group:
                await self.current_processing_msg.edit_text(status_msg)
            else:
                await context.bot.send_message(chat_id=ADMIN_ID, text=status_msg)
            
            downloaded_files = await self.download_all_images(image_links)
            if not downloaded_files:
                return False, "❌ Failed to download images"
            
            # Determine target chat - use original chat_id if processing in group, otherwise use TARGET_GROUP
            target_chat = GROUP_ID if is_group else TARGET_GROUP
            logger.info(f"Preparing to send {len(downloaded_files)} images to chat {target_chat}")
            
            success_count = await self.send_images_in_batches(context, target_chat, downloaded_files)
            
            self.clean_temp_folder()
            
            # Increment processed count and check if we need to send remaining links
            self.processed_count += 1
            if self.processed_count % 5 == 0:
                await self.get_remain_links_auto(context)
            
            return True, f"✅ Downloaded {len(downloaded_files)}/{len(image_links)} images\n✅ Sent {success_count} images to {'group' if is_group else 'target channel'}"
            
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            return False, f"❌ Error processing {url}: {str(e)}"

    async def get_remain_links_auto(self, context: ContextTypes.DEFAULT_TYPE):
        """Automatically send remaining links as text file (internal use)"""
        if not self.link_queue:
            return
            
        # Create a temporary file with all remaining links
        file_path = os.path.join(TEMPORARY_FOLDER, "remaining_links.txt")
        with open(file_path, 'w') as f:
            for url, _, _ in self.link_queue:
                f.write(f"{url}\n")
                
        # Send the file
        with open(file_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=f,
                caption=f"📋 Auto-remain after 5 links: {len(self.link_queue)} links remaining in queue"
            )
            
        # Delete the temporary file
        os.unlink(file_path)

    async def process_link_queue(self, context: ContextTypes.DEFAULT_TYPE):
        """Process all links in the queue"""
        self.processing = True
        self.paused = False
        
        while self.link_queue and self.processing:
            url, chat_id, is_group = self.link_queue.pop(0)
            
            initial_status = f"🔍 Processing: {url}\n📊 Remaining links: {len(self.link_queue)}"
            if is_group:
                self.current_processing_msg = await context.bot.send_message(chat_id=chat_id, text=initial_status)
            else:
                self.current_processing_msg = await context.bot.send_message(chat_id=ADMIN_ID, text=initial_status)
            
            success, result_msg = await self.process_single_link(context, url, chat_id, is_group)
            
            final_msg = f"{result_msg}\n\n📊 Remaining links: {len(self.link_queue)}"
            if is_group:
                await self.current_processing_msg.edit_text(final_msg)
            else:
                await context.bot.send_message(chat_id=ADMIN_ID, text=final_msg)
            
            if self.link_queue and not self.over_mode:
                await asyncio.sleep(DELAY_BETWEEN_LINKS)
        
        self.processing = False
        self.current_processing_msg = None
        self.processed_count = 0  # Reset counter when queue is empty
        
        # If we were in over mode and finished, restore the original queue
        if self.over_mode and not self.link_queue:
            self.link_queue = self.saved_queue
            self.saved_queue = []
            self.over_mode = False
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ Over mode completed! Restored original queue.")
        
        if not self.link_queue and not self.over_mode:
            await context.bot.send_message(chat_id=ADMIN_ID, text="✅ All links processed!")

    async def add_links_to_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE, urls, is_group=False):
        """Add links to processing queue"""
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        new_links = [(url, chat_id, is_group) for url in urls if url.strip()]
        self.link_queue.extend(new_links)
        
        reply_text = f"📥 Added {len(new_links)} link(s) to queue.\n\n📊 Total in queue: {len(self.link_queue)}"
        if not self.processing:
            reply_text += "\n\n🚀 Starting processing..."
            asyncio.create_task(self.process_link_queue(context))
        
        await update.message.reply_text(reply_text)

    async def clean_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear all links from the queue"""
        if update.message.from_user.id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
            
        self.link_queue = []
        self.saved_queue = []
        self.processing = False
        self.paused = False
        self.over_mode = False
        self.processed_count = 0
        
        if self.current_processing_msg:
            try:
                await self.current_processing_msg.edit_text("🛑 Queue cleared and processing stopped.")
            except:
                pass
                
        await update.message.reply_text("🧹 Queue cleared and processing stopped.")

    async def process_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process a URL sent by user"""
        user_id = update.message.from_user.id
        chat_id = update.message.chat.id
        
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        if update.message.document:
            urls = await self.process_text_file(update, context)
            await self.add_links_to_queue(update, context, urls, chat_id == GROUP_ID)
            return
        
        text = update.message.text.strip()
        urls = [url.strip() for url in text.split() if url.strip()]
        await self.add_links_to_queue(update, context, urls, chat_id == GROUP_ID)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        user_id = update.message.from_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
            
        await update.message.reply_text(
            '👋 Hi! I\'m Image Downloader Bot.\n\n'
            'Send me URLs and I\'ll extract images:\n'
            '- Send in group to post there directly\n'
            '- Send privately to forward to target group\n'
            '- Send multiple URLs at once\n'
            '- Send a .txt file with one URL per line\n\n'
            'Commands:\n'
            '/stopnow - Pause processing\n'
            '/startnow - Resume processing\n'
            '/list - Show current queue\n'
            '/clean - Clear all queued links\n'
            '/remain - Get remaining links as text file\n'
            '/over - Pause current job and process new links\n'
            '/overstop - Stop over mode and resume previous job\n\n'
            'Admin only.'
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send help message"""
        user_id = update.message.from_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
            
        await update.message.reply_text(
            'ℹ️ How to use:\n\n'
            '1. Send URLs (multiple allowed):\n'
            '   - In group: Posts images directly\n'
            '   - Privately: Forwards to target group\n'
            '2. Or send a .txt file with URLs (one per line)\n'
            '3. Bot processes one URL at a time with 5s delay\n'
            '4. Shows remaining queue count\n'
            '5. Automatically sends remaining links after every 5 processed links\n\n'
            'Commands:\n'
            '/stopnow - Pause processing\n'
            '/startnow - Resume processing\n'
            '/list - Show current queue\n'
            '/clean - Clear all queued links\n'
            '/remain - Get remaining links as text file\n'
            '/over - Pause current job and process new links\n'
            '/overstop - Stop over mode and resume previous job\n'
            '/help - Show this message'
        )

    async def stop_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause processing"""
        if update.message.from_user.id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
            
        self.paused = True
        await update.message.reply_text("⏸ Processing paused. Use /startnow to resume.")

    async def start_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resume processing"""
        if update.message.from_user.id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
            
        if not self.processing and self.link_queue:
            self.paused = False
            self.processing = True
            asyncio.create_task(self.process_link_queue(context))
            await update.message.reply_text("▶️ Processing resumed!")
        elif self.paused:
            self.paused = False
            await update.message.reply_text("▶️ Processing resumed!")
        else:
            await update.message.reply_text("ℹ️ No links in queue or already processing.")

    async def list_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current queue status"""
        if update.message.from_user.id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
            
        if not self.link_queue:
            await update.message.reply_text("ℹ️ No links in queue.")
            return
            
        message = "📋 Current Queue:\n\n"
        for i, (url, _, _) in enumerate(self.link_queue[:10], 1):
            message += f"{i}. {url}\n"
            
        if len(self.link_queue) > 10:
            message += f"\n...and {len(self.link_queue)-10} more links"
            
        message += f"\n\n📊 Total links remaining: {len(self.link_queue)}"
        
        if self.paused:
            message += "\n\n⏸ Processing is currently paused"
        elif self.processing:
            message += "\n\n▶️ Processing is active"
        else:
            message += "\n\n🛑 Processing is not running"
            
        if self.over_mode:
            message += "\n\n⚠️ OVER MODE ACTIVE - processing temporary links"
            
        await update.message.reply_text(message)

    async def get_remain_links(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a text file with all remaining links in queue"""
        if update.message.from_user.id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
            
        if not self.link_queue:
            await update.message.reply_text("ℹ️ No links in queue.")
            return
            
        # Create a temporary file with all remaining links
        file_path = os.path.join(TEMPORARY_FOLDER, "remaining_links.txt")
        with open(file_path, 'w') as f:
            for url, _, _ in self.link_queue:
                f.write(f"{url}\n")
                
        # Send the file
        with open(file_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.message.chat.id,
                document=f,
                caption=f"📋 Remaining {len(self.link_queue)} links in queue"
            )
            
        # Delete the temporary file
        os.unlink(file_path)

    async def over_mode_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start over mode - save current queue and process new links"""
        if update.message.from_user.id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
            
        if self.over_mode:
            await update.message.reply_text("⚠️ Already in over mode. Send links to process them immediately.")
            return
            
        # Save current queue and clear it
        self.saved_queue = self.link_queue.copy()
        self.link_queue = []
        self.over_mode = True
        self.processed_count = 0
        
        await update.message.reply_text(
            "⚠️ OVER MODE ACTIVATED\n\n"
            "Current queue saved. Now you can send links to process them immediately.\n"
            "When done, use /overstop to return to previous queue."
        )

    async def over_mode_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop over mode and restore previous queue"""
        if update.message.from_user.id != ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
            
        if not self.over_mode:
            await update.message.reply_text("ℹ️ Not in over mode.")
            return
            
        # Restore the original queue
        self.link_queue = self.saved_queue
        self.saved_queue = []
        self.over_mode = False
        self.processed_count = 0
        
        if self.link_queue:
            await update.message.reply_text(
                "✅ Over mode stopped. Original queue restored.\n"
                f"📊 {len(self.link_queue)} links remaining in queue."
            )
            
            if not self.processing:
                self.processing = True
                asyncio.create_task(self.process_link_queue(context))
        else:
            await update.message.reply_text(
                "✅ Over mode stopped. No links in original queue."
            )

async def post_init(application: Application) -> None:
    """Post initialization cleanup"""
    bot = application.bot_data.get('bot')
    if bot:
        bot.clean_temp_folder()

def main():
    """Start the bot."""
    application = Application.builder().token(TOKEN).post_init(post_init).build()

    bot = ImageDownloaderBot()
    application.bot_data['bot'] = bot

    # Command handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help))
    application.add_handler(CommandHandler("stopnow", bot.stop_now))
    application.add_handler(CommandHandler("startnow", bot.start_now))
    application.add_handler(CommandHandler("list", bot.list_queue))
    application.add_handler(CommandHandler("clean", bot.clean_queue))
    application.add_handler(CommandHandler("remain", bot.get_remain_links))
    application.add_handler(CommandHandler("over", bot.over_mode_start))
    application.add_handler(CommandHandler("overstop", bot.over_mode_stop))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.process_url))
    application.add_handler(MessageHandler(filters.Document.TXT, bot.process_url))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
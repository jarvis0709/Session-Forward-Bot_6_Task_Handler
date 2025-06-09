import os
import re
import json
import asyncio
from telethon import TelegramClient, events
from decouple import config
import logging
from telethon.sessions import StringSession
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument
from typing import Dict, Optional, List, Tuple
from collections import defaultdict
import tempfile
from datetime import datetime

# Configure logging
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Read configuration from environment variables
APP_ID = config("API_ID", cast=int)
API_HASH = config("API_HASH")
SESSION = config("SESSION", default="", cast=str)

# Bot configuration
YOUR_ADMIN_USER_ID = config("YOUR_ADMIN_USER_ID", cast=int)
SOURCE_CHANNEL_ID = config("SOURCE_CHANNEL_ID", cast=int)
DOWNLOADER_BOT_USERNAME = config("DOWNLOADER_BOT_USERNAME")
FILE_STORE_BOT_USERNAME = config("FILE_STORE_BOT_USERNAME")
DESTINATION_CHANNEL_ID = config("DESTINATION_CHANNEL_ID", cast=int)

# Constants
CONFIG_FILE = "config.json"
TERABOX_REGEX = r"(?:https?://(?:www\.)?(?:1024terabox\.com|terabox\.com|teraboxlink\.com|terafileshare\.com|teraboxshare\.com|teraboxapp\.com)/\S+)"
MAX_PROCESS_TIME = 180  # 3 minutes timeout

# Enhanced queue and tracking systems
class LinkProcessor:
    def __init__(self):
        self.processing_queue = asyncio.Queue()
        self.current_processing = None
        self.link_status = {}  # Track status of each link
        self.link_thumbnail_map = {}
        self.file_store_responses = {}
        self.processing_lock = asyncio.Lock()
        
    async def add_to_queue(self, link: str, text: str, thumbnail: Optional[bytes] = None):
        """Add a new link to the processing queue."""
        item = {
            'link': link,
            'text': text,
            'thumbnail': thumbnail,
            'timestamp': datetime.now(),
            'status': 'queued'
        }
        self.link_status[link] = item
        await self.processing_queue.put(item)
        logger.info(f"Added link to queue: {link}")
        
    async def process_next(self):
        """Process the next item in the queue."""
        while True:
            try:
                async with self.processing_lock:
                    if self.current_processing:
                        await asyncio.sleep(1)
                        continue
                        
                    item = await self.processing_queue.get()
                    self.current_processing = item
                    link = item['link']
                    
                    logger.info(f"Starting to process link: {link}")
                    item['status'] = 'processing'
                    
                    try:
                        # Process with timeout
                        await asyncio.wait_for(
                            self._process_single_item(item),
                            timeout=MAX_PROCESS_TIME
                        )
                        logger.info(f"Successfully processed link: {link}")
                        item['status'] = 'completed'
                        
                    except asyncio.TimeoutError:
                        logger.error(f"Processing timeout for link: {link}")
                        item['status'] = 'timeout'
                        
                    except Exception as e:
                        logger.error(f"Error processing link {link}: {str(e)}")
                        item['status'] = 'failed'
                        
                    finally:
                        # Cleanup
                        if link in self.link_thumbnail_map:
                            del self.link_thumbnail_map[link]
                        self.current_processing = None
                        self.processing_queue.task_done()
                        
            except Exception as e:
                logger.error(f"Queue processor error: {str(e)}")
                await asyncio.sleep(1)
                
    async def _process_single_item(self, item):
        """Process a single queue item with proper tracking."""
        link = item['link']
        text = item['text']
        thumbnail = item['thumbnail']
        
        if thumbnail:
            self.link_thumbnail_map[link] = thumbnail
            
        # Create completion event for this item
        complete_event = asyncio.Event()
        self.link_status[link]['complete_event'] = complete_event
        
        try:
            # Send to downloader bot
            sent_msg = await client.send_message(
                DOWNLOADER_BOT_USERNAME,
                text
            )
            
            if sent_msg:
                msg_id = sent_msg.id
                self.file_store_responses[msg_id] = {
                    'original_link': link,
                    'last_message_time': asyncio.get_event_loop().time(),
                    'complete_event': complete_event
                }
                logger.info(f"Sent to downloader bot, tracking message ID: {msg_id}")
                
                # Wait for completion
                await complete_event.wait()
                
        except Exception as e:
            logger.error(f"Error processing item {link}: {str(e)}")
            raise

# Initialize processor
link_processor = LinkProcessor()

class Config:
    def __init__(self):
        self.load_config()

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {
                "source_channel": SOURCE_CHANNEL_ID,
                "destination_channel": DESTINATION_CHANNEL_ID,
                "downloader_bot": DOWNLOADER_BOT_USERNAME,
                "file_store_bot": FILE_STORE_BOT_USERNAME
            }
            self.save_config()

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.data, f, indent=4)

    def update_config(self, key: str, value: str):
        self.data[key] = value
        self.save_config()

config_manager = Config()

# Initialize Telethon client
try:
    client = TelegramClient(StringSession(SESSION), APP_ID, API_HASH)
except Exception as ap:
    logging.error(f"Error initializing Telethon client: {ap}")
    exit(1)

async def extract_terabox_links(text: str) -> List[str]:
    """Extract Terabox links from text without modifying them."""
    # Use non-capturing groups (?:) to match but not modify the links
    pattern = r'(?:https?://(?:www\.)?(?:1024terabox\.com|terabox\.com|teraboxlink\.com|terafileshare\.com|teraboxshare\.com|teraboxapp\.com)/\S+)'
    matches = re.finditer(pattern, text)
    return [match.group(0) for match in matches]  # Return exact matches without modification

async def process_thumbnail(message: Message) -> Optional[bytes]:
    """Extract thumbnail from message if available."""
    try:
        if message.media:
            if isinstance(message.media, MessageMediaPhoto):
                # For photos, download the photo itself
                return await message.download_media(bytes)
            elif isinstance(message.media, MessageMediaDocument):
                # For documents/videos, get the thumbnail
                if message.media.document.thumbs:
                    return await message.client.download_file(
                        message.media.document.thumbs[0],
                        bytes
                    )
        return None
    except Exception as e:
        logger.error(f"Error processing thumbnail: {str(e)}")
        return None

async def process_message(event: Message):
    """Process incoming messages from source channel."""
    try:
        text = event.message.text or event.message.caption or ""
        terabox_links = await extract_terabox_links(text)
        
        if not terabox_links:
            return

        logger.info(f"Found {len(terabox_links)} Terabox links in message")
        
        # Get thumbnail if available
        thumbnail = None
        if event.message.media:
            try:
                thumbnail = await event.message.download_media(bytes)
                logger.info("Successfully saved thumbnail from source message")
            except Exception as e:
                logger.error(f"Error saving thumbnail: {str(e)}")
        
        # Add each link to the processing queue
        for link in terabox_links:
            await link_processor.add_to_queue(link, text, thumbnail)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        logger.exception("Full traceback:")

async def handle_file_store_response(event: Message):
    """Handle responses from the file store bot."""
    try:
        # Get message text/caption
        file_store_message = event.message.text or event.message.caption
        
        # Check if this is a file store link message
        if file_store_message and "ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ" in file_store_message:
            # Find the most recent pending file store response
            current_time = asyncio.get_event_loop().time()
            recent_response = None
            recent_id = None
            
            # Find the most recent pending response within last 60 seconds
            for msg_id, data in link_processor.file_store_responses.items():
                if current_time - data['last_message_time'] < 60:  # Within last 60 seconds
                    if not recent_response or data['last_message_time'] > link_processor.file_store_responses[recent_id]['last_message_time']:
                        recent_response = data
                        recent_id = msg_id
            
            if recent_response:
                try:
                    # Get the original thumbnail for this link
                    original_link = recent_response.get('original_link')
                    if original_link and original_link in link_processor.link_thumbnail_map:
                        thumbnail_data = link_processor.link_thumbnail_map[original_link]
                        logger.info(f"Found saved thumbnail for link: {original_link}")
                        
                        # Create temporary file for the saved thumbnail
                        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_thumb:
                            temp_thumb.write(thumbnail_data)
                            temp_thumb.flush()
                            
                            # Send the saved thumbnail with file store link as caption
                            await client.send_file(
                                entity=DESTINATION_CHANNEL_ID,
                                file=temp_thumb.name,
                                caption=file_store_message,
                                parse_mode='html',
                                force_document=False
                            )
                            logger.info("Successfully sent original thumbnail with file store link")
                            
                            # Cleanup
                            os.unlink(temp_thumb.name)
                            
                    else:
                        # If no thumbnail found, send just the message
                        await client.send_message(
                            DESTINATION_CHANNEL_ID,
                            file_store_message,
                            parse_mode='html'
                        )
                        logger.info("Sent file store link (no thumbnail available)")
                    
                    # Mark as complete and cleanup
                    if recent_response.get('complete_event'):
                        recent_response['complete_event'].set()
                    
                    if recent_id in link_processor.file_store_responses:
                        del link_processor.file_store_responses[recent_id]
                    
                except Exception as e:
                    logger.error(f"Error sending to destination: {str(e)}")
                    # Fallback: send just the message
                    await client.send_message(
                        DESTINATION_CHANNEL_ID,
                        file_store_message,
                        parse_mode='html'
                    )
            else:
                logger.warning("No recent file store response found to process")
                
    except Exception as e:
        logger.error(f"Error handling file store response: {str(e)}")
        logger.exception("Full traceback:")

@client.on(events.NewMessage(pattern='/start'))
async def start_command(event: Message):
    """Handle /start command."""
    if event.sender_id != YOUR_ADMIN_USER_ID:
        return
        
    await event.reply(
        "Bot is running!\n\n"
        "Available commands:\n"
        "/set_source <channel_id>\n"
        "/set_destination <channel_id>\n"
        "/set_downloader_bot <username>\n"
        "/set_file_store_bot <username>\n"
        "/get_config"
    )

@client.on(events.NewMessage(pattern=r'/set_source (.+)'))
async def set_source(event: Message):
    """Set source channel ID."""
    if event.sender_id != YOUR_ADMIN_USER_ID:
        return
        
    channel_id = event.pattern_match.group(1)
    config_manager.update_config('source_channel', channel_id)
    await event.reply(f"Source channel updated to: {channel_id}")

@client.on(events.NewMessage(pattern=r'/set_destination (.+)'))
async def set_destination(event: Message):
    """Set destination channel ID."""
    if event.sender_id != YOUR_ADMIN_USER_ID:
        return
        
    channel_id = event.pattern_match.group(1)
    config_manager.update_config('destination_channel', channel_id)
    await event.reply(f"Destination channel updated to: {channel_id}")

@client.on(events.NewMessage(pattern=r'/set_downloader_bot (.+)'))
async def set_downloader_bot(event: Message):
    """Set downloader bot username."""
    if event.sender_id != YOUR_ADMIN_USER_ID:
        return
        
    username = event.pattern_match.group(1)
    config_manager.update_config('downloader_bot', username)
    await event.reply(f"Downloader bot updated to: {username}")

@client.on(events.NewMessage(pattern=r'/set_file_store_bot (.+)'))
async def set_file_store_bot(event: Message):
    """Set file store bot username."""
    if event.sender_id != YOUR_ADMIN_USER_ID:
        return
        
    username = event.pattern_match.group(1)
    config_manager.update_config('file_store_bot', username)
    await event.reply(f"File store bot updated to: {username}")

@client.on(events.NewMessage(pattern='/get_config'))
async def get_config(event: Message):
    """Get current configuration."""
    if event.sender_id != YOUR_ADMIN_USER_ID:
        return
        
    config_text = json.dumps(config_manager.data, indent=2)
    await event.reply(f"Current configuration:\n```\n{config_text}\n```")

# Register event handlers
client.add_event_handler(
    process_message,
    events.NewMessage(chats=SOURCE_CHANNEL_ID)
)

client.add_event_handler(
    handle_file_store_response,
    events.NewMessage(from_users=FILE_STORE_BOT_USERNAME)
)

async def main():
    """Main function to run the bot."""
    try:
        print("Bot has started.")
        
        # Start the queue processor
        queue_processor = asyncio.create_task(link_processor.process_next())
        
        # Start the client
        await client.start()
        
        # Run until disconnected
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())

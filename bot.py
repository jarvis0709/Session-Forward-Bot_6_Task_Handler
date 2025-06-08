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
PROCESSING_QUEUE = asyncio.Queue()
LINK_THUMBNAIL_MAP: Dict[str, bytes] = {}
PENDING_DOWNLOADS: Dict[str, asyncio.Event] = {}
FILE_STORE_RESPONSES: Dict[int, dict] = {}

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
    if message.media:
        if isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument)):
            return await message.download_media(bytes)
    return None

async def process_message(event: Message):
    """Process incoming messages from source channel."""
    try:
        text = event.message.text or event.message.caption or ""
        terabox_links = await extract_terabox_links(text)
        
        if not terabox_links:
            return

        # Get thumbnail from the message
        thumbnail = await process_thumbnail(event.message)
        
        for link in terabox_links:
            if thumbnail:
                LINK_THUMBNAIL_MAP[link] = thumbnail
            
            # Add to processing queue with original text and link
            await PROCESSING_QUEUE.put({
                'link': link,
                'msg_id': event.id,
                'text': text,
                'thumbnail': thumbnail
            })
            logger.info(f"Added Terabox link to queue: {link}")

    except Exception as e:
        logger.error(f"Error processing message: {e}")

async def process_queue():
    """Process queued Terabox links."""
    while True:
        try:
            data = await PROCESSING_QUEUE.get()
            link = data['link']
            original_text = data['text']
            thumbnail = data.get('thumbnail')
            
            logger.info(f"Processing queue item for link: {link}")
            
            # Send link to downloader bot
            sent_msg = await client.send_message(DOWNLOADER_BOT_USERNAME, original_text)
            
            if sent_msg:
                # Store info for later use
                FILE_STORE_RESPONSES[sent_msg.id] = {
                    'event': asyncio.Event(),
                    'original_link': link,
                    'thumbnail': thumbnail
                }
                
                logger.info(f"Sent to downloader bot with message ID: {sent_msg.id}")
                
                # Wait for the complete process (with timeout)
                try:
                    await asyncio.wait_for(FILE_STORE_RESPONSES[sent_msg.id]['event'].wait(), timeout=180)
                    logger.info(f"Successfully processed link: {link}")
                except asyncio.TimeoutError:
                    logger.error(f"Timeout waiting for complete process: {link}")
                finally:
                    # Clean up
                    if sent_msg.id in FILE_STORE_RESPONSES:
                        del FILE_STORE_RESPONSES[sent_msg.id]
            
            PROCESSING_QUEUE.task_done()
            
        except Exception as e:
            logger.error(f"Error processing queue item: {e}")
        
        # Rate limiting
        await asyncio.sleep(2)

async def handle_downloader_response(event: Message):
    """Handle responses from the downloader bot."""
    try:
        # Check if the message has media and is a document
        if event.media and isinstance(event.media, MessageMediaDocument):
            mime_type = event.media.document.mime_type
            # Check if it's a video or document
            if mime_type.startswith('video/') or not mime_type.startswith('image/'):
                logger.info("Found valid media file, forwarding to file store bot")
                # Forward to file store bot
                forwarded = await event.forward_to(FILE_STORE_BOT_USERNAME)
                
                # Store message info for tracking
                FILE_STORE_RESPONSES[forwarded.id] = {
                    'event': asyncio.Event(),
                    'original_link': None,  # Will be set when processing file store response
                    'thumbnail': None  # Will store thumbnail data
                }
                
                logger.info(f"Forwarded to file store bot with message ID: {forwarded.id}")
            else:
                logger.debug("Ignored non-video/document media from downloader bot")
        else:
            logger.debug("Ignored non-media message from downloader bot")
                
    except Exception as e:
        logger.error(f"Error handling downloader response: {e}")

@client.on(events.NewMessage(from_users=FILE_STORE_BOT_USERNAME))
async def handle_file_store_response(event: Message):
    """Handle responses from the file store bot."""
    try:
        logger.info("Received response from file store bot")
        
        # Check if this is a reply to our forwarded message
        if event.reply_to:
            original_msg_id = event.reply_to.reply_to_msg_id
            logger.info(f"Response is for message ID: {original_msg_id}")
            
            # Check if we're waiting for this response
            if original_msg_id in FILE_STORE_RESPONSES:
                response_data = FILE_STORE_RESPONSES[original_msg_id]
                
                # Get the complete message from file store bot
                file_store_message = event.message.text or event.message.caption
                
                if file_store_message and "ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ" in file_store_message:
                    logger.info("Found file store link message, forwarding to destination")
                    
                    # Get the original thumbnail
                    original_link = response_data.get('original_link')
                    thumbnail = LINK_THUMBNAIL_MAP.get(original_link) if original_link else None
                    
                    try:
                        # Forward the complete message to destination
                        await client.send_message(
                            DESTINATION_CHANNEL_ID,
                            file_store_message,  # Complete formatted message
                            file=thumbnail if thumbnail else None
                        )
                        logger.info("Successfully forwarded file store message to destination")
                    except Exception as e:
                        logger.error(f"Error forwarding to destination: {e}")
                    
                    # Clean up
                    if original_link in LINK_THUMBNAIL_MAP:
                        del LINK_THUMBNAIL_MAP[original_link]
                
                # Signal completion
                response_data['event'].set()
                del FILE_STORE_RESPONSES[original_msg_id]
                
    except Exception as e:
        logger.error(f"Error handling file store response: {e}")

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
    handle_downloader_response,
    events.NewMessage(from_users=DOWNLOADER_BOT_USERNAME)
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
        queue_processor = asyncio.create_task(process_queue())
        
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

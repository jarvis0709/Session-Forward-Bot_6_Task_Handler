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
        
        # First get the thumbnail from source message
        thumbnail = None
        if event.message.media:
            try:
                thumbnail = await event.message.download_media(bytes)
                logger.info("Successfully saved thumbnail from source message")
            except Exception as e:
                logger.error(f"Error saving thumbnail: {str(e)}")
        
        for link in terabox_links:
            if thumbnail:
                LINK_THUMBNAIL_MAP[link] = thumbnail
                logger.info(f"Mapped thumbnail to Terabox link: {link}")
            
            # Send to downloader bot
            try:
                sent_msg = await client.send_message(
                    DOWNLOADER_BOT_USERNAME,
                    text
                )
                if sent_msg:
                    # Store message ID and link mapping for tracking
                    FILE_STORE_RESPONSES[sent_msg.id] = {
                        'original_link': link,
                        'last_message_time': asyncio.get_event_loop().time()
                    }
                    logger.info(f"Sent to downloader bot, tracking message ID: {sent_msg.id}")
            except Exception as e:
                logger.error(f"Error sending to downloader bot: {str(e)}")

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        logger.exception("Full traceback:")

async def process_queue():
    """Process queued Terabox links."""
    while True:
        try:
            data = await PROCESSING_QUEUE.get()
            link = data['link']
            original_text = data['text']
            
            # Send link to downloader bot with original text
            download_event = asyncio.Event()
            PENDING_DOWNLOADS[link] = download_event
            
            # Send the original text containing the link
            sent_msg = await client.send_message(DOWNLOADER_BOT_USERNAME, original_text)
            
            # Store the original link for later use with file store response
            if sent_msg.id in FILE_STORE_RESPONSES:
                FILE_STORE_RESPONSES[sent_msg.id]['original_link'] = link
            
            logger.info(f"Sent original message to downloader bot containing link: {link}")
            
            # Wait for download (with timeout)
            try:
                await asyncio.wait_for(download_event.wait(), timeout=180)
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for download: {link}")
                
            PROCESSING_QUEUE.task_done()
            
        except Exception as e:
            logger.error(f"Error processing queue: {e}")
        
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
                # Forward to file store bot
                forwarded = await event.forward_to(FILE_STORE_BOT_USERNAME)
                if forwarded:
                    logger.info(f"Forwarded file to file store bot with ID: {forwarded.id}")
                    
                    # Transfer the tracking data to new message ID
                    if event.reply_to and event.reply_to.reply_to_msg_id in FILE_STORE_RESPONSES:
                        original_data = FILE_STORE_RESPONSES[event.reply_to.reply_to_msg_id]
                        FILE_STORE_RESPONSES[forwarded.id] = {
                            'original_link': original_data['original_link'],
                            'last_message_time': asyncio.get_event_loop().time()
                        }
                else:
                    logger.error("Failed to forward to file store bot")

    except Exception as e:
        logger.error(f"Error handling downloader response: {str(e)}")

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
            for msg_id, data in FILE_STORE_RESPONSES.items():
                if current_time - data['last_message_time'] < 60:  # Within last 60 seconds
                    if not recent_response or data['last_message_time'] > FILE_STORE_RESPONSES[recent_id]['last_message_time']:
                        recent_response = data
                        recent_id = msg_id
            
            if recent_response:
                try:
                    # Get the original thumbnail for this link
                    original_link = recent_response.get('original_link')
                    if original_link and original_link in LINK_THUMBNAIL_MAP:
                        thumbnail_data = LINK_THUMBNAIL_MAP[original_link]
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
                            del LINK_THUMBNAIL_MAP[original_link]
                    else:
                        # If no thumbnail found, send just the message
                        await client.send_message(
                            DESTINATION_CHANNEL_ID,
                            file_store_message,
                            parse_mode='html'
                        )
                        logger.info("Sent file store link (no thumbnail available)")
                    
                    # Cleanup tracking data
                    if recent_id in FILE_STORE_RESPONSES:
                        del FILE_STORE_RESPONSES[recent_id]
                    
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

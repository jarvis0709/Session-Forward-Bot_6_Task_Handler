import os
import re
import json
import asyncio
from telethon import TelegramClient, events
from decouple import config
import logging
from telethon.sessions import StringSession
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument, DocumentAttributeSticker
from typing import Dict, Optional, List, Tuple
from collections import defaultdict
import tempfile
from telethon.helpers import strip_text

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
TERABOX_REGEX = r"(?:https?://(?:www\.)?(?:1024terabox\.com|terabox\.com|terasharelink\.com|teraboxlink\.com|terafileshare\.com|teraboxshare\.com|teraboxapp\.com)/\S+)"
MESSAGE_QUEUE = asyncio.Queue()  # Queue for all source channel messages
LINK_QUEUE = asyncio.Queue()    # Queue for messages with Terabox links
LINK_THUMBNAIL_MAP: Dict[str, bytes] = {}
PENDING_DOWNLOADS: Dict[str, asyncio.Event] = {}
FILE_STORE_RESPONSES: Dict[int, dict] = {}
CURRENT_PROCESSING = None
PROCESSING_LOCK = asyncio.Lock()

# Allowed MIME types for forwarding
ALLOWED_MIME_TYPES = {
    'video/', 
    'audio/',
    'application/',  # For general files
}

def is_allowed_media(message: Message) -> bool:
    """Check if the media type is allowed for forwarding."""
    if not message.media or not isinstance(message.media, MessageMediaDocument):
        return False
        
    document = message.media.document
    
    # Skip stickers
    for attr in document.attributes:
        if isinstance(attr, DocumentAttributeSticker):
            return False
            
    mime_type = document.mime_type
    
    # Only allow videos, audio, and general files
    return (
        mime_type.startswith('video/') or 
        mime_type.startswith('audio/') or 
        mime_type.startswith('application/')
    )

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

async def extract_terabox_links(message: Message) -> List[str]:
    """Extract Terabox links from message text."""
    if not message.text and not message.caption:
        return []
        
    # Get text and entities from message
    text = message.text or message.caption
    
    # Handle bold/formatted text by getting raw text
    if message.entities:
        text = message.raw_text
        
    pattern = r'(?:https?://(?:www\.)?(?:1024terabox\.com|terabox\.com|teraboxlink\.com|terafileshare\.com|teraboxshare\.com|teraboxapp\.com)/\S+)'
    matches = re.finditer(pattern, text)
    return [match.group(0) for match in matches]

async def process_message(event: Message):
    """Queue incoming messages from source channel."""
    try:
        # Add every message to queue immediately
        await MESSAGE_QUEUE.put(event.message)
        logger.info("Added new message to queue")
    except Exception as e:
        logger.error(f"Error queueing message: {e}")
        logger.exception("Full traceback:")

async def message_processor():
    """Process messages from MESSAGE_QUEUE and check for Terabox links."""
    while True:
        try:
            # Get message from queue
            message = await MESSAGE_QUEUE.get()
            
            # Extract links
            terabox_links = await extract_terabox_links(message)
            
            if terabox_links:
                logger.info(f"Found {len(terabox_links)} Terabox links in message")
                
                # Get thumbnail if available
                thumbnail = None
                if message.media:
                    try:
                        thumbnail = await message.download_media(bytes)
                        logger.info("Successfully saved thumbnail from source message")
                    except Exception as e:
                        logger.error(f"Error saving thumbnail: {str(e)}")
                
                # Add each link separately to the queue with same thumbnail
                for link in terabox_links:
                    await LINK_QUEUE.put({
                        'link': link,
                        'text': message.text or message.caption or "",
                        'thumbnail': thumbnail,
                        'original_message': message
                    })
                    logger.info(f"Queued link for processing: {link}")
            else:
                logger.info("No Terabox links found in message, skipping")
            
            MESSAGE_QUEUE.task_done()
            
        except Exception as e:
            logger.error(f"Error in message processor: {e}")
            await asyncio.sleep(1)

async def process_queue():
    """Process queued Terabox links."""
    global CURRENT_PROCESSING
    
    while True:
        try:
            async with PROCESSING_LOCK:
                if CURRENT_PROCESSING:
                    await asyncio.sleep(1)
                    continue
                    
                data = await LINK_QUEUE.get()
                CURRENT_PROCESSING = data
                link = data['link']
                text = data['text']
                thumbnail = data['thumbnail']
                
                try:
                    # Process with timeout for complete operation
                    await asyncio.wait_for(
                        process_single_link(link, text, thumbnail),
                        timeout=150  # 2.5 minutes timeout for complete operation
                    )
                    logger.info(f"Successfully processed link: {link}")
                    # No fixed delay - proceed to next link immediately
                    
                except asyncio.TimeoutError:
                    logger.error(f"Processing timeout for link: {link}")
                    # Cleanup on timeout
                    if link in LINK_THUMBNAIL_MAP:
                        del LINK_THUMBNAIL_MAP[link]
                    if link in PENDING_DOWNLOADS:
                        del PENDING_DOWNLOADS[link]
                    # Clean up any associated file store responses
                    for msg_id, data in list(FILE_STORE_RESPONSES.items()):
                        if data.get('original_link') == link:
                            del FILE_STORE_RESPONSES[msg_id]
                    
                except Exception as e:
                    logger.error(f"Error processing link {link}: {str(e)}")
                    
                finally:
                    CURRENT_PROCESSING = None
                    LINK_QUEUE.task_done()
                    
        except Exception as e:
            logger.error(f"Queue processor error: {str(e)}")
            await asyncio.sleep(1)

async def process_single_link(link: str, text: str, thumbnail: Optional[bytes] = None):
    """Process a single link with all steps."""
    try:
        if thumbnail:
            LINK_THUMBNAIL_MAP[link] = thumbnail
            logger.info(f"Mapped thumbnail to Terabox link: {link}")
        
        # Send only the link to downloader bot
        sent_msg = await client.send_message(
            DOWNLOADER_BOT_USERNAME,
            link  # Only send the link, not the full caption
        )
        
        if sent_msg:
            # Store message ID and link mapping for tracking
            FILE_STORE_RESPONSES[sent_msg.id] = {
                'original_link': link,
                'last_message_time': asyncio.get_event_loop().time(),
                'original_text': text  # Store original text for later use
            }
            logger.info(f"Sent to downloader bot, tracking message ID: {sent_msg.id}")
            
            # Create and wait for download event
            download_event = asyncio.Event()
            PENDING_DOWNLOADS[link] = download_event
            await download_event.wait()
            
    except Exception as e:
        logger.error(f"Error in process_single_link: {str(e)}")
        raise

async def handle_downloader_response(event: Message):
    """Handle responses from the downloader bot."""
    try:
        # Check if the message has media and is allowed type
        if event.media and is_allowed_media(event):
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
        else:
            logger.info("Skipping non-allowed media type or sticker")

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
        
        # Start the message and link processors
        message_processor_task = asyncio.create_task(message_processor())
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

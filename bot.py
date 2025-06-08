import os
import re
import json
import asyncio
import tempfile
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
LINK_THUMBNAIL_MAP: Dict[str, str] = {}  # Now stores file paths instead of bytes
FILE_STORE_RESPONSES: Dict[int, dict] = {}

# Create temp directory for thumbnails
TEMP_DIR = tempfile.mkdtemp()
logger.info(f"Created temporary directory at: {TEMP_DIR}")

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

async def save_thumbnail(message: Message) -> Optional[str]:
    """Save thumbnail from message to a temporary file."""
    try:
        if message.media:
            if isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument)):
                logger.info("Downloading media for thumbnail")
                # Generate a unique filename
                temp_path = os.path.join(TEMP_DIR, f"thumb_{message.id}.jpg")
                # Download as file
                await message.download_media(temp_path)
                logger.info(f"Saved thumbnail to: {temp_path}")
                return temp_path
    except Exception as e:
        logger.error(f"Error in save_thumbnail: {e}")
    return None

async def process_message(event: Message):
    """Process incoming messages from source channel."""
    try:
        logger.info("Received new message from source channel")
        text = event.message.text or event.message.caption or ""
        logger.info(f"Message content: {text}")

        terabox_links = await extract_terabox_links(text)
        
        if not terabox_links:
            logger.debug("No Terabox links found in message")
            return

        logger.info(f"Found {len(terabox_links)} Terabox links in message")
        
        # Save thumbnail if available
        thumbnail_path = None
        try:
            if event.media:
                logger.info("Message contains media, attempting to save thumbnail")
                thumbnail_path = await save_thumbnail(event.message)
                if thumbnail_path:
                    logger.info(f"Successfully saved thumbnail to: {thumbnail_path}")
        except Exception as e:
            logger.error(f"Error saving thumbnail: {e}")

        for link in terabox_links:
            logger.info(f"Processing Terabox link: {link}")
            if thumbnail_path:
                LINK_THUMBNAIL_MAP[link] = thumbnail_path
                logger.info(f"Stored thumbnail path for link: {thumbnail_path}")

            try:
                # Send to downloader bot
                logger.info("Sending message to downloader bot")
                sent_msg = await client.send_message(
                    DOWNLOADER_BOT_USERNAME,
                    text
                )
                
                if sent_msg:
                    logger.info(f"Successfully sent message to downloader bot with ID: {sent_msg.id}")
                    
                    # Store response tracker
                    FILE_STORE_RESPONSES[sent_msg.id] = {
                        'event': asyncio.Event(),
                        'original_link': link,
                        'thumbnail_path': thumbnail_path,
                        'original_text': text
                    }
                else:
                    logger.error("Failed to send message to downloader bot")

            except Exception as e:
                logger.error(f"Error sending to downloader bot: {e}")

    except Exception as e:
        logger.error(f"Error in process_message: {e}")

async def process_queue():
    """Process queued Terabox links."""
    while True:
        try:
            data = await PROCESSING_QUEUE.get()
            link = data['link']
            original_text = data['text']
            thumbnail_path = data.get('thumbnail_path')
            
            logger.info(f"Processing queue item for link: {link}")
            
            # Send link to downloader bot
            sent_msg = await client.send_message(DOWNLOADER_BOT_USERNAME, original_text)
            
            if sent_msg:
                # Store info for later use
                FILE_STORE_RESPONSES[sent_msg.id] = {
                    'event': asyncio.Event(),
                    'original_link': link,
                    'thumbnail_path': thumbnail_path
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
        logger.info("Received response from downloader bot")
        
        if not event.media:
            logger.debug("Response has no media, skipping")
            return
            
        if not isinstance(event.media, MessageMediaDocument):
            logger.debug("Response media is not a document, skipping")
            return
            
        mime_type = event.media.document.mime_type
        logger.info(f"Received media with mime type: {mime_type}")
        
        # Check if it's a video or document
        if mime_type.startswith('video/') or not mime_type.startswith('image/'):
            logger.info("Valid media file found, forwarding to file store bot")
            try:
                # Forward to file store bot
                forwarded = await event.forward_to(FILE_STORE_BOT_USERNAME)
                logger.info(f"Successfully forwarded to file store bot with ID: {forwarded.id}")
                
                # Store message info for tracking
                FILE_STORE_RESPONSES[forwarded.id] = {
                    'event': asyncio.Event(),
                    'original_link': None,
                    'thumbnail_path': None
                }
                
            except Exception as e:
                logger.error(f"Error forwarding to file store bot: {e}")
        else:
            logger.debug(f"Skipping media with mime type: {mime_type}")
                
    except Exception as e:
        logger.error(f"Error in handle_downloader_response: {e}")

@client.on(events.NewMessage(from_users=FILE_STORE_BOT_USERNAME))
async def handle_file_store_response(event: Message):
    """Handle responses from the file store bot."""
    try:
        logger.info("Received message from file store bot")
        message_text = event.message.text or event.message.caption
        logger.info(f"Message content: {message_text}")
        
        if not event.reply_to:
            logger.debug("Not a reply message, skipping")
            return
            
        original_msg_id = event.reply_to.reply_to_msg_id
        logger.info(f"Reply to message ID: {original_msg_id}")
        
        if original_msg_id not in FILE_STORE_RESPONSES:
            logger.debug("Message ID not found in tracking, skipping")
            return
            
        response_data = FILE_STORE_RESPONSES[original_msg_id]
        
        if not message_text:
            logger.debug("No message content, skipping")
            return
            
        if "ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ" in message_text:
            logger.info("Found file store link message")
            
            try:
                # Get the thumbnail path
                original_link = response_data.get('original_link')
                thumbnail_path = LINK_THUMBNAIL_MAP.get(original_link)
                
                if thumbnail_path and os.path.exists(thumbnail_path):
                    logger.info(f"Found thumbnail at path: {thumbnail_path}")
                    
                    try:
                        # Send thumbnail with caption
                        await client.send_file(
                            entity=DESTINATION_CHANNEL_ID,
                            file=thumbnail_path,
                            caption=message_text,
                            parse_mode='md'
                        )
                        logger.info("Successfully sent message with thumbnail to destination")
                        
                        # Clean up thumbnail file
                        os.remove(thumbnail_path)
                        logger.info(f"Deleted thumbnail file: {thumbnail_path}")
                        
                    except Exception as e:
                        logger.error(f"Error sending with thumbnail: {e}")
                        # Try sending just the message
                        await client.send_message(
                            DESTINATION_CHANNEL_ID,
                            message_text,
                            parse_mode='md'
                        )
                        logger.info("Sent message without thumbnail to destination")
                else:
                    logger.info("No thumbnail available, sending text only")
                    await client.send_message(
                        DESTINATION_CHANNEL_ID,
                        message_text,
                        parse_mode='md'
                    )
                    logger.info("Sent message without thumbnail to destination")
                
                # Cleanup
                if original_link in LINK_THUMBNAIL_MAP:
                    del LINK_THUMBNAIL_MAP[original_link]
                    
            except Exception as e:
                logger.error(f"Error forwarding to destination: {e}")
        
        # Signal completion and cleanup
        response_data['event'].set()
        del FILE_STORE_RESPONSES[original_msg_id]
        
    except Exception as e:
        logger.error(f"Error in handle_file_store_response: {e}")

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
    events.NewMessage(from_users=DOWNLOADER_BOT_USERNAME, incoming=True)
)

client.add_event_handler(
    handle_file_store_response,
    events.NewMessage(from_users=FILE_STORE_BOT_USERNAME)
)

async def main():
    """Main function to run the bot."""
    try:
        print("Bot has started.")
        logger.info("Bot is starting up")
        
        # Start the client
        await client.start()
        logger.info("Client started successfully")
        
        # Run until disconnected
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        await client.disconnect()
        logger.info("Bot has been stopped")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())

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

# Initialize the client
client = TelegramClient(StringSession(SESSION), APP_ID, API_HASH)

# Create temp directory for thumbnails
TEMP_DIR = tempfile.mkdtemp()
logger.info(f"Created temporary directory for thumbnails at: {TEMP_DIR}")

# Data structures for mapping relationships
class LinkData:
    def __init__(self, terabox_link: str, thumbnail_path: Optional[str] = None):
        self.terabox_link = terabox_link
        self.thumbnail_path = thumbnail_path
        self.download_msg_id = None
        self.file_store_msg_id = None
        self.event = asyncio.Event()

# Global mappings
LINK_DATA: Dict[str, LinkData] = {}  # terabox_link -> LinkData
MSG_TO_LINK: Dict[int, str] = {}  # message_id -> terabox_link

async def extract_terabox_links(text: str) -> List[str]:
    """Extract Terabox links from text."""
    pattern = r"(?:https?://(?:www\.)?(?:1024terabox\.com|terabox\.com|teraboxlink\.com|terafileshare\.com|teraboxshare\.com|teraboxapp\.com)/\S+)"
    matches = re.finditer(pattern, text)
    return [match.group(0) for match in matches]

async def save_thumbnail(message: Message, link: str) -> Optional[str]:
    """Save thumbnail from message and associate with Terabox link."""
    try:
        if message.media:
            if isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument)):
                # Generate unique filename using link hash
                filename = f"thumb_{hash(link)}.jpg"
                temp_path = os.path.join(TEMP_DIR, filename)
                
                logger.info(f"Saving thumbnail for link {link}")
                await message.download_media(temp_path)
                logger.info(f"Thumbnail saved at: {temp_path}")
                return temp_path
    except Exception as e:
        logger.error(f"Error saving thumbnail: {e}")
    return None

async def process_message(event: Message):
    """Process incoming messages from source channel."""
    try:
        logger.info("Processing new message from source channel")
        text = event.message.text or event.message.caption or ""
        
        # Extract Terabox links
        terabox_links = await extract_terabox_links(text)
        if not terabox_links:
            return
        
        logger.info(f"Found {len(terabox_links)} Terabox links")
        
        for link in terabox_links:
            # Save thumbnail if available
            thumbnail_path = await save_thumbnail(event.message, link) if event.media else None
            
            # Create LinkData object
            link_data = LinkData(link, thumbnail_path)
            LINK_DATA[link] = link_data
            
            logger.info(f"Created mapping for link {link}" + 
                       f" with thumbnail: {thumbnail_path if thumbnail_path else 'None'}")
            
            # Send to downloader bot
            try:
                sent_msg = await client.send_message(
                    DOWNLOADER_BOT_USERNAME,
                    text
                )
                if sent_msg:
                    link_data.download_msg_id = sent_msg.id
                    MSG_TO_LINK[sent_msg.id] = link
                    logger.info(f"Sent to downloader bot, message ID: {sent_msg.id}")
            except Exception as e:
                logger.error(f"Error sending to downloader bot: {e}")

    except Exception as e:
        logger.error(f"Error in process_message: {e}")

async def handle_downloader_response(event: Message):
    """Handle responses from the downloader bot."""
    try:
        logger.info(f"Received response from downloader bot - Message ID: {event.id}")
        
        # First check if this is a media message
        if not event.media:
            logger.info("Message contains no media, skipping...")
            return
            
        # Check if this is a response to our message
        if not event.reply_to:
            logger.info("Message is not a reply, skipping...")
            return
            
        original_msg_id = event.reply_to.reply_to_msg_id
        logger.info(f"Original message ID: {original_msg_id}")
        
        if original_msg_id not in MSG_TO_LINK:
            logger.info(f"Message ID {original_msg_id} not found in MSG_TO_LINK mapping")
            return
            
        terabox_link = MSG_TO_LINK[original_msg_id]
        link_data = LINK_DATA.get(terabox_link)
        
        if not link_data:
            logger.error(f"No LinkData found for message ID: {original_msg_id}")
            return
            
        logger.info(f"Processing downloaded content for link: {terabox_link}")
        
        # Forward to file store bot
        try:
            logger.info("Attempting to forward to file store bot...")
            forwarded = await event.forward_to(FILE_STORE_BOT_USERNAME)
            if forwarded:
                link_data.file_store_msg_id = forwarded.id
                MSG_TO_LINK[forwarded.id] = terabox_link
                logger.info(f"Successfully forwarded to file store bot, message ID: {forwarded.id}")
            else:
                logger.error("Failed to forward message to file store bot")
        except Exception as e:
            logger.error(f"Error forwarding to file store bot: {str(e)}")

    except Exception as e:
        logger.error(f"Error in handle_downloader_response: {str(e)}")
        logger.exception("Full traceback:")

@client.on(events.NewMessage(from_users=FILE_STORE_BOT_USERNAME))
async def handle_file_store_response(event: Message):
    """Handle responses from the file store bot."""
    try:
        if not event.reply_to:
            return
            
        original_msg_id = event.reply_to.reply_to_msg_id
        if original_msg_id not in MSG_TO_LINK:
            return
            
        terabox_link = MSG_TO_LINK[original_msg_id]
        link_data = LINK_DATA.get(terabox_link)
        
        if not link_data:
            logger.error(f"No LinkData found for file store response")
            return
            
        message_text = event.message.text or event.message.caption
        if not message_text or "ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ" not in message_text:
            return
            
        logger.info(f"Received file store link for Terabox link: {terabox_link}")
        
        try:
            if link_data.thumbnail_path and os.path.exists(link_data.thumbnail_path):
                # Send thumbnail with file store link as caption
                await client.send_file(
                    entity=DESTINATION_CHANNEL_ID,
                    file=link_data.thumbnail_path,
                    caption=message_text,
                    parse_mode='md'
                )
                logger.info("Sent thumbnail with file store link to destination")
                
                # Clean up thumbnail
                os.remove(link_data.thumbnail_path)
                logger.info(f"Deleted thumbnail: {link_data.thumbnail_path}")
            else:
                # Send just the file store link
                await client.send_message(
                    DESTINATION_CHANNEL_ID,
                    message_text,
                    parse_mode='md'
                )
                logger.info("Sent file store link to destination (no thumbnail)")
            
            # Clean up mappings
            del LINK_DATA[terabox_link]
            del MSG_TO_LINK[original_msg_id]
            if link_data.download_msg_id in MSG_TO_LINK:
                del MSG_TO_LINK[link_data.download_msg_id]
            logger.info("Cleaned up mappings")
            
        except Exception as e:
            logger.error(f"Error sending to destination: {e}")

    except Exception as e:
        logger.error(f"Error in handle_file_store_response: {e}")

# Register event handlers
client.add_event_handler(
    process_message,
    events.NewMessage(chats=SOURCE_CHANNEL_ID)
)

client.add_event_handler(
    handle_downloader_response,
    events.NewMessage(from_users=DOWNLOADER_BOT_USERNAME, incoming=True)
)

async def main():
    """Main function to run the bot."""
    try:
        logger.info("Bot is starting up")
        await client.start()
        logger.info("Client started successfully")
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Clean up temp directory on shutdown
        try:
            for file in os.listdir(TEMP_DIR):
                os.remove(os.path.join(TEMP_DIR, file))
            os.rmdir(TEMP_DIR)
            logger.info("Cleaned up temporary directory")
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}")
        await client.disconnect()
        logger.info("Bot has been stopped")

if __name__ == "__main__":
    asyncio.run(main())

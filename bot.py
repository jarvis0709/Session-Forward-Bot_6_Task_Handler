import os
from telethon import TelegramClient, events
from decouple import config
import logging
from telethon.sessions import StringSession
import asyncio

# Configure logging
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)

# Read configuration from environment variables
APP_ID = config("API_ID", cast=int)
API_HASH = config("API_HASH")
SESSION = config("SESSION", default="", cast=str)

BLOCKED_TEXTS = config("BLOCKED_TEXTS", default="", cast=lambda x: [i.strip().lower() for i in x.split(',')])
YOUR_ADMIN_USER_ID = config("YOUR_ADMIN_USER_ID", default=0, cast=int)
BOT_API_KEY = config("BOT_API_KEY", default="", cast=str)

# Initialize Telethon client
try:
    steallootdealUser = TelegramClient(StringSession(SESSION), APP_ID, API_HASH)
    steallootdealUser.start()
except Exception as ap:
    logging.error(f"Error initializing Telethon client: {ap}")
    exit(1)

# Define source and destination channels
SOURCE_CHANNEL_1 = os.environ.get("SOURCE_CHANNEL_1", "-1001927159396")
SOURCE_CHANNEL_2 = os.environ.get("SOURCE_CHANNEL_2", "-1001821993662")
SOURCE_CHANNEL_3 = os.environ.get("SOURCE_CHANNEL_3", "-1002406125694")
SOURCE_CHANNEL_4 = os.environ.get("SOURCE_CHANNEL_4", "-1002240663497")
SOURCE_CHANNEL_5 = os.environ.get("SOURCE_CHANNEL_5", "-1001741122061")
SOURCE_CHANNEL_6 = os.environ.get("SOURCE_CHANNEL_6", "-1002471218322")
SOURCE_CHANNEL_7 = os.environ.get("SOURCE_CHANNEL_7", "-1002392738204")
SOURCE_CHANNEL_8 = os.environ.get("SOURCE_CHANNEL_8", "-1002422209369")
SOURCE_CHANNEL_9 = os.environ.get("SOURCE_CHANNEL_9", "-1002271035070")

DESTINATION_CHANNEL_1 = os.environ.get("DESTINATION_CHANNEL_1", "-1002349374753")
DESTINATION_CHANNEL_2 = os.environ.get("DESTINATION_CHANNEL_2", "-1002488212445")
DESTINATION_CHANNEL_3 = os.environ.get("DESTINATION_CHANNEL_3", "-1002488212445")
DESTINATION_CHANNEL_4 = os.environ.get("DESTINATION_CHANNEL_4", "-1002377412867")
DESTINATION_CHANNEL_5 = os.environ.get("DESTINATION_CHANNEL_5", "-1002402818813")
DESTINATION_CHANNEL_6 = os.environ.get("DESTINATION_CHANNEL_6", "-1002488212445")
DESTINATION_CHANNEL_7 = os.environ.get("DESTINATION_CHANNEL_7", "-1002377412867")
DESTINATION_CHANNEL_8 = os.environ.get("DESTINATION_CHANNEL_8", "-1002377412867")
DESTINATION_CHANNEL_9 = os.environ.get("DESTINATION_CHANNEL_9", "-1002348514977")

class ChannelIDs:
    def __init__(self):
        self.source_channel_1 = [int(i.strip()) for i in SOURCE_CHANNEL_1.replace(",", " ").split()]
        self.source_channel_2 = [int(i.strip()) for i in SOURCE_CHANNEL_2.replace(",", " ").split()]
        self.source_channel_3 = [int(i.strip()) for i in SOURCE_CHANNEL_3.replace(",", " ").split()]
        self.source_channel_4 = [int(i.strip()) for i in SOURCE_CHANNEL_4.replace(",", " ").split()]
        self.source_channel_5 = [int(i.strip()) for i in SOURCE_CHANNEL_5.replace(",", " ").split()]
        self.source_channel_6 = [int(i.strip()) for i in SOURCE_CHANNEL_6.replace(",", " ").split()]
        self.source_channel_7 = [int(i.strip()) for i in SOURCE_CHANNEL_7.replace(",", " ").split()]
        self.source_channel_8 = [int(i.strip()) for i in SOURCE_CHANNEL_8.replace(",", " ").split()]
        self.source_channel_9 = [int(i.strip()) for i in SOURCE_CHANNEL_9.replace(",", " ").split()]
        self.destination_channel_1 = [int(i.strip()) for i in DESTINATION_CHANNEL_1.replace(",", " ").split()]
        self.destination_channel_2 = [int(i.strip()) for i in DESTINATION_CHANNEL_2.replace(",", " ").split()]
        self.destination_channel_3 = [int(i.strip()) for i in DESTINATION_CHANNEL_3.replace(",", " ").split()]
        self.destination_channel_4 = [int(i.strip()) for i in DESTINATION_CHANNEL_4.replace(",", " ").split()]
        self.destination_channel_5 = [int(i.strip()) for i in DESTINATION_CHANNEL_5.replace(",", " ").split()]
        self.destination_channel_6 = [int(i.strip()) for i in DESTINATION_CHANNEL_6.replace(",", " ").split()]
        self.destination_channel_7 = [int(i.strip()) for i in DESTINATION_CHANNEL_7.replace(",", " ").split()]
        self.destination_channel_8 = [int(i.strip()) for i in DESTINATION_CHANNEL_8.replace(",", " ").split()]
        self.destination_channel_9 = [int(i.strip()) for i in DESTINATION_CHANNEL_9.replace(",", " ").split()]

    def get_source_destination_map(self):
        return {
            self.source_channel_1[0]: self.destination_channel_1,
            self.source_channel_2[0]: self.destination_channel_2,
            self.source_channel_3[0]: self.destination_channel_3,
            self.source_channel_4[0]: self.destination_channel_4,
            self.source_channel_5[0]: self.destination_channel_5,
            self.source_channel_6[0]: self.destination_channel_6,
            self.source_channel_7[0]: self.destination_channel_7,
            self.source_channel_8[0]: self.destination_channel_8,
            self.source_channel_9[0]: self.destination_channel_9,
        }

channel_ids = ChannelIDs()
SOURCE_DESTINATION_MAP = channel_ids.get_source_destination_map()

# Forward message as copy (no forward tag, preserves formatting & media)
async def sender_bH(event):
    try:
        source_channel = int(event.chat_id)
        destination_channels = SOURCE_DESTINATION_MAP.get(source_channel, [])

        if event.raw_text:
            message_text = event.raw_text.lower()
            if any(blocked_text in message_text for blocked_text in BLOCKED_TEXTS):
                logging.warning(f"Blocked message containing one of the specified texts: {event.raw_text}")
                return

        tasks = [
            asyncio.create_task(
                steallootdealUser.forward_messages(dest_channel, event.message, as_copy=True)
            ) for dest_channel in destination_channels
        ]
        await asyncio.gather(*tasks)
        logging.info(f"Message copied (as-is) to: {destination_channels}")

    except Exception as e:
        logging.error(f"Error handling incoming message: {e}")

# Register event handler
source_channels = (
    channel_ids.source_channel_1 +
    channel_ids.source_channel_2 +
    channel_ids.source_channel_3 +
    channel_ids.source_channel_4 +
    channel_ids.source_channel_5 +
    channel_ids.source_channel_6 +
    channel_ids.source_channel_7 +
    channel_ids.source_channel_8 +
    channel_ids.source_channel_9
)

steallootdealUser.add_event_handler(sender_bH, events.NewMessage(incoming=True, chats=source_channels))

# Run the bot
print("Bot has started and is running...")
steallootdealUser.run_until_disconnected()

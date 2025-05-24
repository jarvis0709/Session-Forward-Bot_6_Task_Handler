import os
from telethon import TelegramClient, events
from decouple import config
import logging
from telethon.sessions import StringSession

# Configure logging
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)

# Read configuration from environment variables
APP_ID = config("API_ID", cast=int)
API_HASH = config("API_HASH")
SESSION = config("SESSION", default="", cast=str)

# Define blocked texts and media forwarding response
BLOCKED_TEXTS = config("BLOCKED_TEXTS", default="", cast=lambda x: [i.strip().lower() for i in x.split(',')])
MEDIA_FORWARD_RESPONSE = config("MEDIA_FORWARD_RESPONSE", default="yes").lower()

# Define admin user ID and bot API key
YOUR_ADMIN_USER_ID = config("YOUR_ADMIN_USER_ID", default=0, cast=int)
BOT_API_KEY = config("BOT_API_KEY", default="", cast=str)

# Initialize Telethon client
try:
    steallootdealUser  = TelegramClient(StringSession(SESSION), APP_ID, API_HASH)
    steallootdealUser .start()
except Exception as ap:
    logging.error(f"Error initializing Telethon client: {ap}")
    exit(1)

# Define source and destination channels
SOURCE_CHANNEL_1 = os.environ.get("SOURCE_CHANNEL_1", "-1001927159396") #HollyWoodMovies
SOURCE_CHANNEL_2 = os.environ.get("SOURCE_CHANNEL_2", "-1001821993662") #𝐏𝐫𝐞𝐦𝐢𝐮𝐦𝐡𝐮𝐛
SOURCE_CHANNEL_3 = os.environ.get("SOURCE_CHANNEL_3", "-1002406125694") #SOUTHMOVIECRUSH
SOURCE_CHANNEL_4 = os.environ.get("SOURCE_CHANNEL_4", "-1002240663497") #TopViralLinks
SOURCE_CHANNEL_5 = os.environ.get("SOURCE_CHANNEL_5", "-1001741122061") #DamselMovieDownload
SOURCE_CHANNEL_6 = os.environ.get("SOURCE_CHANNEL_6", "-1002471218322") #AllSouthHindidubbedmovies
SOURCE_CHANNEL_7 = os.environ.get("SOURCE_CHANNEL_7", "-1002392738204") #1_adult
SOURCE_CHANNEL_8 = os.environ.get("SOURCE_CHANNEL_8", "-1002420223835") #TV
SOURCE_CHANNEL_9 = os.environ.get("SOURCE_CHANNEL_9", "-1002271035070") #testmmfilelog

DESTINATION_CHANNEL_1 = os.environ.get("DESTINATION_CHANNEL_1", "-1002349374753") #HollyWoodMovies
DESTINATION_CHANNEL_2 = os.environ.get("DESTINATION_CHANNEL_2", "-1002488212445") #IndianMoviesForward
DESTINATION_CHANNEL_3 = os.environ.get("DESTINATION_CHANNEL_3", "-1002488212445") #IndianMoviesForward
DESTINATION_CHANNEL_4 = os.environ.get("DESTINATION_CHANNEL_4", "-1002377412867") #TheVideoForward
DESTINATION_CHANNEL_5 = os.environ.get("DESTINATION_CHANNEL_5", "-1002402818813") #ExtraChannel
DESTINATION_CHANNEL_6 = os.environ.get("DESTINATION_CHANNEL_6", "-1002488212445") #IndianMoviesForward
DESTINATION_CHANNEL_7 = os.environ.get("DESTINATION_CHANNEL_7", "-1002377412867") #TheVideoForward
DESTINATION_CHANNEL_8 = os.environ.get("DESTINATION_CHANNEL_8", "-1002176533426") #TV
DESTINATION_CHANNEL_9 = os.environ.get("DESTINATION_CHANNEL_9", "-1002348514977") #TestDemo3

class ChannelIDs:
    def __init__(self):
        # Split by comma or space and convert to integers
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
            # Add more source-destination pairs as needed
 }

channel_ids = ChannelIDs()
SOURCE_DESTINATION_MAP = channel_ids.get_source_destination_map()

# Event handler for incoming messages
# Event handler for incoming messages
async def sender_bH(event):
    try:
        source_channel = str(event.chat_id)
        destination_channels = SOURCE_DESTINATION_MAP.get(int(source_channel), [])

        for dest_channel in destination_channels:
            try:
                message_text = event.raw_text.lower()

                if any(blocked_text in message_text for blocked_text in BLOCKED_TEXTS):
                    logging.warning(f"Blocked message containing one of the specified texts: {event.raw_text}")
                    continue

                if event.media:
                    user_response = MEDIA_FORWARD_RESPONSE
                    if user_response != 'yes':
                        logging.info(f"Media forwarding skipped by user for message: {event.raw_text}")
                        continue

                    await steallootdealUser .send_message(dest_channel, message_text, file=event.media)
                    logging.info(f"Forwarded media message to channel {dest_channel}")

                else:
                    await steallootdealUser .send_message(dest_channel, message_text)
                    logging.info(f"Forwarded text message to channel {dest_channel}")

            except Exception as e:
                logging.error(f"Error forwarding message to channel {dest_channel}: {e}")

    except Exception as e:
        logging.error(f"Error handling incoming message: {e}")

# Register event handler
source_channels = channel_ids.source_channel_1 + channel_ids.source_channel_2 + channel_ids.source_channel_3 + channel_ids.source_channel_4 + channel_ids.source_channel_5 + channel_ids.source_channel_6 + channel_ids.source_channel_7 + channel_ids.source_channel_8 + channel_ids.source_channel_9
steallootdealUser .add_event_handler(sender_bH, events.NewMessage(incoming=True, chats=source_channels))

# Run the bot
print("Bot has started.")
steallootdealUser .run_until_disconnected()

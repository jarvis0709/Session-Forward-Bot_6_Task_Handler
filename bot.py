
import os
from telethon import TelegramClient, events
from decouple import config
import logging
from telethon.sessions import StringSession
import asyncio

# Configure logging
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)
logging.info("Logging configured.")

# Initialize message queue
message_queue = asyncio.Queue()

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
    steallootdealUser     = TelegramClient(StringSession(SESSION), APP_ID, API_HASH)
    steallootdealUser    .start()
except Exception as ap:
    logging.error(f"Error initializing Telethon client: {ap}")
    exit(1)

# Define source and destination channels
SOURCE_CHANNEL_1 = os.environ.get("SOURCE_CHANNEL_1", "-1002436625087") #All Hollywood movies
SOURCE_CHANNEL_2 = os.environ.get("SOURCE_CHANNEL_2", "-1001950252875") #Movie_mania
SOURCE_CHANNEL_3 = os.environ.get("SOURCE_CHANNEL_3", "-1002045229088") #Movie_house
SOURCE_CHANNEL_4 = os.environ.get("SOURCE_CHANNEL_4", "-1002603982843") #Japaneas_hub
SOURCE_CHANNEL_5 = os.environ.get("SOURCE_CHANNEL_5", "-1001741122061") #DamselMovieDownload
SOURCE_CHANNEL_6 = os.environ.get("SOURCE_CHANNEL_6", "-1002336841751") #All South Hindi dubbed movies
SOURCE_CHANNEL_7 = os.environ.get("SOURCE_CHANNEL_7", "-1002607828329") #Instagram_links
SOURCE_CHANNEL_8 = os.environ.get("SOURCE_CHANNEL_8", "-1002092938265") #Tera special Collectionn
SOURCE_CHANNEL_9 = os.environ.get("SOURCE_CHANNEL_9", "-1002271035070") #testmmfilelog

DESTINATION_CHANNEL_1 = os.environ.get("DESTINATION_CHANNEL_1", "-1002349374753") #HollyWoodMovies
DESTINATION_CHANNEL_2 = os.environ.get("DESTINATION_CHANNEL_2", "-1002488212445") #IndianMoviesForward
DESTINATION_CHANNEL_3 = os.environ.get("DESTINATION_CHANNEL_3", "-1002488212445") #IndianMoviesForward
DESTINATION_CHANNEL_4 = os.environ.get("DESTINATION_CHANNEL_4", "-1002377412867") #TheVideoForward
DESTINATION_CHANNEL_5 = os.environ.get("DESTINATION_CHANNEL_5", "-1002402818813") #ExtraChannel
DESTINATION_CHANNEL_6 = os.environ.get("DESTINATION_CHANNEL_6", "-1002488212445") #IndianMoviesForward
DESTINATION_CHANNEL_7 = os.environ.get("DESTINATION_CHANNEL_7", "-1002377412867") #TheVideoForward
DESTINATION_CHANNEL_8 = os.environ.get("DESTINATION_CHANNEL_8", "-1002377412867") #TheVideoForward
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
async def sender_bH(event):
    logging.info(f"sender_bH triggered for event from chat: {event.chat_id}, message ID: {event.message.id}")
    try:
        await message_queue.put(event)
        logging.info(f"Message ID {event.message.id} from chat {event.chat_id} added to queue.")
    except Exception as e:
        logging.error(f"Error in sender_bH adding message to queue: {e}")

# Message processor
async def message_processor():
    logging.info("Message processor task started.")
    while True:
        logging.info("Message processor loop iteration started, waiting for message from queue...")
        try:
            event = await message_queue.get()
            logging.info(f"Message processor retrieved message ID {event.message.id} from chat {event.chat_id} from queue.")
            source_channel_id = event.chat_id
            destination_channels = SOURCE_DESTINATION_MAP.get(source_channel_id, [])

            if not destination_channels:
                logging.info(f"No destination configured for source channel {source_channel_id}. Message ID {event.message.id} dropped after retrieval from queue.")
                message_queue.task_done()
                continue

            logging.info(f"Processing message ID {event.message.id} from {source_channel_id} for destinations: {destination_channels}")
            
            tasks = []
            for dest_channel in destination_channels:
                try:
                    # Check for blocked text using lowercase version of the message
                    if event.raw_text and any(blocked_text in event.raw_text.lower() for blocked_text in BLOCKED_TEXTS):
                        logging.warning(f"Blocked message ID {event.message.id} from {source_channel_id} containing one of the specified texts: {event.raw_text}")
                        continue

                    # For media messages, check if forwarding is allowed
                    if event.media and MEDIA_FORWARD_RESPONSE != 'yes':
                        logging.info(f"Media forwarding skipped by user for message ID {event.message.id} from {source_channel_id}")
                        continue

                    # Forward the message as is, dropping the author to remove the forward tag
                    task = asyncio.create_task(steallootdealUser.forward_messages(dest_channel, event.message, drop_author=True))
                    tasks.append(task)
                    logging.info(f"Forwarding message ID {event.message.id} from {source_channel_id} to channel {dest_channel} without forward tag")

                except Exception as e:
                    logging.error(f"Error forwarding message ID {event.message.id} from {source_channel_id} to channel {dest_channel}: {e}")
            
            if tasks:
                await asyncio.gather(*tasks)
            
            message_queue.task_done()
            logging.info(f"Finished processing message ID {event.message.id} from {source_channel_id}.")

        except asyncio.CancelledError:
            logging.info("Message processor task cancelled.")
            break
        except Exception as e:
            logging.error(f"Error in message_processor: {e}")
            await asyncio.sleep(1) # Add a small delay to prevent rapid error loops if persistent errors occur

# Register event handler
source_channels = channel_ids.source_channel_1 + channel_ids.source_channel_2 + channel_ids.source_channel_3 + channel_ids.source_channel_4 + channel_ids.source_channel_5 + channel_ids.source_channel_6 + channel_ids.source_channel_7 + channel_ids.source_channel_8 + channel_ids.source_channel_9
steallootdealUser     .add_event_handler(sender_bH, events.NewMessage(incoming=True, chats=source_channels))

# Start the message processor
steallootdealUser.loop.create_task(message_processor())

# Run the bot
print("Bot has started.")
logging.info("Starting Telethon client run_until_disconnected...")
steallootdealUser     .run_until_disconnected()

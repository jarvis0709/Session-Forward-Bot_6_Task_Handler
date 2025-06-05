import os
import json
import re
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

# New configurations for link processing
LINK_SOURCE_CHANNEL = os.environ.get("LINK_SOURCE_CHANNEL", "-1002823482126") # Channel to monitor for links
LINK_BOT_USERNAME = os.environ.get("LINK_BOT_USERNAME", "Terabox_video_saver_bot") # Bot to send links to
LINK_DEST_CHANNEL = os.environ.get("LINK_DEST_CHANNEL", "-1002224926400") # Channel to forward media files to
LINK_WAIT_TIME = int(os.environ.get("LINK_WAIT_TIME", "180")) # Time to wait for bot response in seconds

# Initialize message queue for bot responses to handle flood limits
bot_response_queue = asyncio.Queue()

# Define mapping file path
MAPPING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mapping.json")

# Initialize Telethon client
try:
    steallootdealUser     = TelegramClient(StringSession(SESSION), APP_ID, API_HASH)
    steallootdealUser    .start()
except Exception as ap:
    logging.error(f"Error initializing Telethon client: {ap}")
    exit(1)

# Define source and destination channels
# SOURCE_CHANNEL_1 = os.environ.get("SOURCE_CHANNEL_1", "-1001927159396") #Ävåïlåßlê
# SOURCE_CHANNEL_2 = os.environ.get("SOURCE_CHANNEL_2", "-1001808135797") #S0uth Mov!e Shorts
# SOURCE_CHANNEL_3 = os.environ.get("SOURCE_CHANNEL_3", "-1002045229088") #Movie_house
# SOURCE_CHANNEL_4 = os.environ.get("SOURCE_CHANNEL_4", "-1002603982843") #Japaneas_hub
# SOURCE_CHANNEL_5 = os.environ.get("SOURCE_CHANNEL_5", "-1001741122061") #DamselMovieDownload
# SOURCE_CHANNEL_6 = os.environ.get("SOURCE_CHANNEL_6", "-1002336841751") #All South Hindi dubbed movies
# SOURCE_CHANNEL_7 = os.environ.get("SOURCE_CHANNEL_7", "-1002607828329") #Instagram_links
# SOURCE_CHANNEL_8 = os.environ.get("SOURCE_CHANNEL_8", "-1002092938265") #Tera special Collectionn
SOURCE_CHANNEL_9 = os.environ.get("SOURCE_CHANNEL_9", "-1002271035070") #testmmfilelog

# DESTINATION_CHANNEL_1 = os.environ.get("DESTINATION_CHANNEL_1", "-1002661425980") #Bypass Hollywood Forward
# DESTINATION_CHANNEL_2 = os.environ.get("DESTINATION_CHANNEL_2", "-1002548718458") #Bypass Indian Forward
# DESTINATION_CHANNEL_3 = os.environ.get("DESTINATION_CHANNEL_3", "-1002488212445") #IndianMoviesForward
# DESTINATION_CHANNEL_4 = os.environ.get("DESTINATION_CHANNEL_4", "-1002377412867") #TheVideoForward
# DESTINATION_CHANNEL_5 = os.environ.get("DESTINATION_CHANNEL_5", "-1002402818813") #ExtraChannel
# DESTINATION_CHANNEL_6 = os.environ.get("DESTINATION_CHANNEL_6", "-1002488212445") #IndianMoviesForward
# DESTINATION_CHANNEL_7 = os.environ.get("DESTINATION_CHANNEL_7", "-1002377412867") #TheVideoForward
# DESTINATION_CHANNEL_8 = os.environ.get("DESTINATION_CHANNEL_8", "-1002377412867") #TheVideoForward
DESTINATION_CHANNEL_9 = os.environ.get("DESTINATION_CHANNEL_9", "-1002348514977") #TestDemo3

class ChannelIDs:
    def __init__(self):
        # Split by comma or space and convert to integers
        # self.source_channel_1 = [int(i.strip()) for i in SOURCE_CHANNEL_1.replace(",", " ").split()]
        # self.source_channel_2 = [int(i.strip()) for i in SOURCE_CHANNEL_2.replace(",", " ").split()]
        # self.source_channel_3 = [int(i.strip()) for i in SOURCE_CHANNEL_3.replace(",", " ").split()]
        # self.source_channel_4 = [int(i.strip()) for i in SOURCE_CHANNEL_4.replace(",", " ").split()]
        # self.source_channel_5 = [int(i.strip()) for i in SOURCE_CHANNEL_5.replace(",", " ").split()]
        # self.source_channel_6 = [int(i.strip()) for i in SOURCE_CHANNEL_6.replace(",", " ").split()]
        # self.source_channel_7 = [int(i.strip()) for i in SOURCE_CHANNEL_7.replace(",", " ").split()]
        # self.source_channel_8 = [int(i.strip()) for i in SOURCE_CHANNEL_8.replace(",", " ").split()]
        self.source_channel_9 = [int(i.strip()) for i in SOURCE_CHANNEL_9.replace(",", " ").split()]
        # self.destination_channel_1 = [int(i.strip()) for i in DESTINATION_CHANNEL_1.replace(",", " ").split()]
        # self.destination_channel_2 = [int(i.strip()) for i in DESTINATION_CHANNEL_2.replace(",", " ").split()]
        # self.destination_channel_3 = [int(i.strip()) for i in DESTINATION_CHANNEL_3.replace(",", " ").split()]
        # self.destination_channel_4 = [int(i.strip()) for i in DESTINATION_CHANNEL_4.replace(",", " ").split()]
        # self.destination_channel_5 = [int(i.strip()) for i in DESTINATION_CHANNEL_5.replace(",", " ").split()]
        # self.destination_channel_6 = [int(i.strip()) for i in DESTINATION_CHANNEL_6.replace(",", " ").split()]
        # self.destination_channel_7 = [int(i.strip()) for i in DESTINATION_CHANNEL_7.replace(",", " ").split()]
        # self.destination_channel_8 = [int(i.strip()) for i in DESTINATION_CHANNEL_8.replace(",", " ").split()]
        self.destination_channel_9 = [int(i.strip()) for i in DESTINATION_CHANNEL_9.replace(",", " ").split()]

    def get_source_destination_map(self):
        # First try to load from mapping.json file
        try:
            if os.path.exists(MAPPING_FILE):
                with open(MAPPING_FILE, 'r') as f:
                    mapping_data = json.load(f)
                    # Convert string keys to integers and string values to integer lists
                    return {int(k): [int(i) for i in v] for k, v in mapping_data.items()}
        except Exception as e:
            logging.error(f"Error loading mapping from file: {e}")
        
        # Fall back to default mapping if file doesn't exist or has errors
        return {
            # self.source_channel_1[0]: self.destination_channel_1,
            # self.source_channel_2[0]: self.destination_channel_2,
            # self.source_channel_3[0]: self.destination_channel_3,
            # self.source_channel_4[0]: self.destination_channel_4,
            # self.source_channel_5[0]: self.destination_channel_5,
            # self.source_channel_6[0]: self.destination_channel_6,
            # self.source_channel_7[0]: self.destination_channel_7,
            # self.source_channel_8[0]: self.destination_channel_8,
            self.source_channel_9[0]: self.destination_channel_9,
            # Add more source-destination pairs as needed
        }

channel_ids = ChannelIDs()
SOURCE_DESTINATION_MAP = channel_ids.get_source_destination_map()

# Function to save mapping to JSON file
def save_mapping_to_file():
    try:
        # Convert integer keys and values to strings for JSON serialization
        mapping_data = {str(k): [str(i) for i in v] for k, v in SOURCE_DESTINATION_MAP.items()}
        with open(MAPPING_FILE, 'w') as f:
            json.dump(mapping_data, f, indent=2)
        logging.info(f"Mapping saved to {MAPPING_FILE}")
        return True
    except Exception as e:
        logging.error(f"Error saving mapping to file: {e}")
        return False

# Create initial mapping file if it doesn't exist
if not os.path.exists(MAPPING_FILE):
    save_mapping_to_file()

# Event handler for incoming messages
async def sender_bH(event):
    if not event or not event.message:
        logging.warning("sender_bH triggered with invalid event object.")
        return

    chat_id = None
    message_id = None
    try:
        chat_id = event.chat_id
        message_id = event.message.id
        logging.info(f"sender_bH triggered for event from chat: {chat_id}, message ID: {message_id}")
    except AttributeError as ae:
        logging.error(f"sender_bH: Error accessing event attributes (chat_id or message.id): {ae}. Event data: {event}")
        return

    try:
        await message_queue.put(event)
        logging.info(f"Message ID {message_id} from chat {chat_id} added to queue. Queue size: {message_queue.qsize()}")
    except Exception as e:
        logging.error(f"Error in sender_bH adding message ID {message_id} from chat {chat_id} to queue: {e}")

async def start_command_handler(event):
    welcome_message = "Hello! I'm your Telegram Forwarder Bot. To start forwarding messages, please ensure the channels are configured correctly.\n\nCommands:\n/setmap <source_id> to <destination_id> - Add mapping\n/removemap <source_id> to <destination_id> - Remove mapping\n/getmap - Show all mappings"
    image_url = "https://ik.imagekit.io/dvnhxw9vq/bot_pic.jpeg?updatedAt=1741960637889"
    try: await event.respond(message=welcome_message, file=image_url)
    except Exception: pass

# Command handler for /setmap
async def setmap_command_handler(event):
    # Check if user is authorized
    if event.sender_id != YOUR_ADMIN_USER_ID:
        await event.respond("❌ Unauthorized: Only admin can use this command.")
        return
    
    try:
        # Parse command: /setmap <source_id> to <destination_id>
        text = event.raw_text.strip()
        match = re.match(r'/setmap\s+(-?\d+)\s+to\s+(-?\d+)', text)
        
        if not match:
            await event.respond("❌ Invalid format. Use: /setmap <source_id> to <destination_id>")
            return
        
        source_id = int(match.group(1))
        destination_id = int(match.group(2))
        
        # Update mapping
        if source_id in SOURCE_DESTINATION_MAP:
            # Check for duplicates
            if destination_id not in SOURCE_DESTINATION_MAP[source_id]:
                SOURCE_DESTINATION_MAP[source_id].append(destination_id)
        else:
            SOURCE_DESTINATION_MAP[source_id] = [destination_id]
        
        # Save to file
        if save_mapping_to_file():
            await event.respond(f"✅ Mapping set: {source_id} → {destination_id}")
        else:
            await event.respond("❌ Error saving mapping to file.")
    
    except Exception as e:
        logging.error(f"Error in setmap_command_handler: {e}")
        await event.respond(f"❌ Error: {str(e)}")

# Command handler for /removemap
async def removemap_command_handler(event):
    # Check if user is authorized
    if event.sender_id != YOUR_ADMIN_USER_ID:
        await event.respond("❌ Unauthorized: Only admin can use this command.")
        return
    
    try:
        # Parse command: /removemap <source_id> to <destination_id>
        text = event.raw_text.strip()
        match = re.match(r'/removemap\s+(-?\d+)\s+to\s+(-?\d+)', text)
        
        if not match:
            await event.respond("❌ Invalid format. Use: /removemap <source_id> to <destination_id>")
            return
        
        source_id = int(match.group(1))
        destination_id = int(match.group(2))
        
        # Check if mapping exists
        if source_id not in SOURCE_DESTINATION_MAP or destination_id not in SOURCE_DESTINATION_MAP[source_id]:
            await event.respond("❌ Mapping not found.")
            return
        
        # Remove mapping
        SOURCE_DESTINATION_MAP[source_id].remove(destination_id)
        
        # If no destinations left, remove the source key
        if not SOURCE_DESTINATION_MAP[source_id]:
            del SOURCE_DESTINATION_MAP[source_id]
        
        # Save to file
        if save_mapping_to_file():
            await event.respond(f"✅ Mapping removed: {source_id} → {destination_id}")
        else:
            await event.respond("❌ Error saving mapping to file.")
    
    except Exception as e:
        logging.error(f"Error in removemap_command_handler: {e}")
        await event.respond(f"❌ Error: {str(e)}")

# Command handler for /getmap
async def getmap_command_handler(event):
    # Check if user is authorized
    if event.sender_id != YOUR_ADMIN_USER_ID:
        await event.respond("❌ Unauthorized: Only admin can use this command.")
        return
    
    try:
        if not SOURCE_DESTINATION_MAP:
            await event.respond("No mappings configured.")
            return
        
        # Format mappings
        mappings_text = "Current Mappings:\n"
        for source_id, destination_ids in SOURCE_DESTINATION_MAP.items():
            destinations = ", ".join([str(d) for d in destination_ids])
            mappings_text += f"{source_id} → {destinations}\n"
        
        await event.respond(mappings_text)
    
    except Exception as e:
        logging.error(f"Error in getmap_command_handler: {e}")
        await event.respond(f"❌ Error: {str(e)}")

# Link processing function
async def process_link(event, link):
    try:
        # Send link to bot
        await steallootdealUser.send_message(LINK_BOT_USERNAME, link)
        logging.info(f"Sent link to bot: {link}")
    except Exception as e:
        logging.error(f"Error sending link to bot: {e}")

# Bot response handler
async def bot_response_handler(event):
    try:
        # Get the sender
        sender = await event.get_sender()
        if not sender:
            return
            
        # Check if message is from our target bot (both by username and id)
        bot_username = LINK_BOT_USERNAME.replace("@", "")
        if (hasattr(sender, 'username') and sender.username == bot_username) or \
           (hasattr(sender, 'id') and str(sender.id) == bot_username):
            # Instead of sending directly, queue the message for processing
            await bot_response_queue.put(event)
            logging.info(f"Queued bot message for processing")
    except Exception as e:
        logging.error(f"Error in bot response handler: {e}")

# Bot response processor to handle flood limits
async def bot_response_processor():
    logging.info("Bot response processor started")
    while True:
        try:
            event = await bot_response_queue.get()
            
            try:
                # Get destination channel entity first
                try:
                    dest_channel = await steallootdealUser.get_entity(int(LINK_DEST_CHANNEL))
                except ValueError as ve:
                    logging.error(f"Invalid channel ID {LINK_DEST_CHANNEL}: {ve}")
                    continue
                except Exception as e:
                    logging.error(f"Could not get channel entity for {LINK_DEST_CHANNEL}: {e}")
                    # Wait and retry once
                    await asyncio.sleep(5)
                    dest_channel = await steallootdealUser.get_entity(int(LINK_DEST_CHANNEL))
                
                # Try to forward the message
                try:
                    await steallootdealUser.send_message(
                        dest_channel,
                        message=event.message.message if event.message.message else None,
                        file=event.message.media if event.message.media else None,
                        reply_to=event.message.reply_to_msg_id if event.message.reply_to_msg_id else None
                    )
                    logging.info(f"Forwarded new message from bot to {LINK_DEST_CHANNEL}")
                except Exception as send_error:
                    # If send fails, try forwarding
                    await steallootdealUser.forward_messages(dest_channel, event.message)
                    logging.info(f"Forwarded message using forward method")
                
                # Add delay between messages to avoid flood wait
                await asyncio.sleep(2)
                
            except Exception as e:
                logging.error(f"Error processing bot message: {e}")
                # If we hit flood wait, wait and retry
                if "flood wait" in str(e).lower():
                    wait_time = int(str(e).split("flood wait of ")[1].split(" seconds")[0])
                    logging.info(f"Hit flood wait, sleeping for {wait_time} seconds")
                    await asyncio.sleep(wait_time)
                    # Re-queue the message
                    await bot_response_queue.put(event)
                
        except Exception as e:
            logging.error(f"Error in bot response processor: {e}")
            await asyncio.sleep(1)
        finally:
            bot_response_queue.task_done()

# Link handler
async def link_handler(event):
    try:
        # Get text from any type of message
        text = ""
        try:
            if hasattr(event.message, 'message'):
                text += event.message.message if event.message.message else ""
        except:
            pass
            
        try:
            if hasattr(event.message, 'caption'):
                text += " " + event.message.caption if event.message.caption else ""
        except:
            pass

        if not text:
            return
            
        # Find all terasharelink.com links in text
        #links = re.findall(r'https?://(?:www\.)?terasharelink\.com/[^\s]+', text)
        links = re.findall(r'https?://(?:www\.)?(?:1024terabox\.com|teraboxlink\.com|terafileshare\.com|terasharelink\.com|teraboxshare\.com|teraboxapp\.com)/[^\s]+', text)

        
        if links:
            logging.info(f"Found terasharelink.com links in message: {links}")
            for link in links:
                await process_link(event, link)
                
    except Exception as e:
        logging.error(f"Error in link handler: {e}")

# Message processor
async def message_processor():
    logging.info("Message processor task started.")
    while True:
        logging.info("Message processor loop iteration started, waiting for message from queue...")
        event = None  # Initialize event to None
        try:
            event = await message_queue.get()
            logging.info(f"Message processor retrieved message ID {event.message.id} from chat {event.chat_id} from queue.")
            source_channel_id = event.chat_id
            destination_channels = SOURCE_DESTINATION_MAP.get(source_channel_id, [])

            if not destination_channels:
                logging.info(f"No destination configured for source channel {source_channel_id}. Message ID {event.message.id} dropped after retrieval from queue.")
                # message_queue.task_done() will be called in finally
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
            
            logging.info(f"Finished processing message ID {event.message.id} from {source_channel_id}.")

        except asyncio.CancelledError:
            logging.info("Message processor task cancelled.")
            if event:  # If event was retrieved before cancellation
                try:
                    message_queue.put_nowait(event)  # Re-queue the event
                    logging.info(f"Re-queued message ID {event.message.id} due to cancellation.")
                except asyncio.QueueFull:
                    logging.error(f"Failed to re-queue message ID {event.message.id} due to cancellation, queue is full.")
            break
        except Exception as e:
            if event:
                logging.error(f"Error in message_processor for message ID {event.message.id}: {e}")
            else:
                logging.error(f"Error in message_processor (event not retrieved): {e}")
            await asyncio.sleep(1)  # Add a small delay to prevent rapid error loops if persistent errors occur
        finally:
            if event:  # Ensure task_done is called only if an event was retrieved and processed (or skipped)
                message_queue.task_done()
                logging.debug(f"message_queue.task_done() called for event from chat {event.chat_id}")

# Register event handlers
async def register_handlers():
    try:
        # Basic handlers
        source_channels = list(SOURCE_DESTINATION_MAP.keys())
        steallootdealUser.add_event_handler(
            sender_bH, 
            events.NewMessage(incoming=True, chats=source_channels)
        )
        
        # Command handlers
        steallootdealUser.add_event_handler(
            start_command_handler, 
            events.NewMessage(pattern=r'^/start$', incoming=True)
        )
        steallootdealUser.add_event_handler(
            setmap_command_handler, 
            events.NewMessage(pattern=r'^/setmap', incoming=True)
        )
        steallootdealUser.add_event_handler(
            removemap_command_handler, 
            events.NewMessage(pattern=r'^/removemap', incoming=True)
        )
        steallootdealUser.add_event_handler(
            getmap_command_handler, 
            events.NewMessage(pattern=r'^/getmap$', incoming=True)
        )
        
        # Link processing handlers
        if LINK_SOURCE_CHANNEL and LINK_BOT_USERNAME and LINK_DEST_CHANNEL:
            logging.info(f"Setting up link processing for source channel {LINK_SOURCE_CHANNEL}")
            # Handler for source channel messages
            steallootdealUser.add_event_handler(
                link_handler, 
                events.NewMessage(chats=int(LINK_SOURCE_CHANNEL))
            )
            
            # Get bot entity to ensure it exists
            bot_entity = await steallootdealUser.get_entity(LINK_BOT_USERNAME)
            if bot_entity:
                logging.info(f"Found bot {LINK_BOT_USERNAME} with id {bot_entity.id}")
                # Handler for bot responses - filter by bot ID
                steallootdealUser.add_event_handler(
                    bot_response_handler,
                    events.NewMessage(from_users=bot_entity.id)
                )
            else:
                logging.error(f"Could not find bot {LINK_BOT_USERNAME}")
        
        logging.info("All handlers registered successfully")
    except Exception as e:
        logging.error(f"Error registering handlers: {e}")
        raise

# Start all tasks
async def start_bot():
    try:
        # Register all event handlers
        await register_handlers()
        
        # Start processors
        steallootdealUser.loop.create_task(message_processor())
        steallootdealUser.loop.create_task(bot_response_processor())
        
        # Log startup
        print("Bot has started.")
        logging.info("Starting Telethon client...")
        
        # Run the bot
        await steallootdealUser.run_until_disconnected()
    except Exception as e:
        logging.error(f"Error starting bot: {e}")
        raise

# Run the bot
if __name__ == "__main__":
    steallootdealUser.loop.run_until_complete(start_bot())
print("Bot has started.")
logging.info("Starting Telethon client run_until_disconnected...")
steallootdealUser.run_until_disconnected()

import logging
import os
import pymongo
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.executor import start_webhook
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Environment variables
API_TOKEN = os.environ['TG_TOKEN']

# webhook settings
WEBHOOK_HOST = 'https://mbard.alwaysdata.net/'
WEBHOOK_PATH = '/bot/'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# webserver settings
WEBAPP_HOST = '::'  # or ip
WEBAPP_PORT = 8333

# MongoDB settings
client = pymongo.MongoClient("mongodb+srv://maksymbardakh:qwerty1234@cluster0.zelrxfe.mongodb.net/TGBotDB?retryWrites=true&w=majority")
db = client.get_database("TGBotDB")
notes_collection = db["Collection_BOT"]

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Bot and Dispatcher initialization
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

class NoteStates(StatesGroup):
    waiting_for_note = State()
    waiting_for_delete_choice = State()

# Function to create a keyboard with buttons
def get_base_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("/add"))
    keyboard.add(KeyboardButton("/notes"))
    keyboard.add(KeyboardButton("/delete"))
    return keyboard

@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply(
        "Hi! I'm your note bot. You can add, view, and delete notes.",
        reply_markup=get_base_keyboard()
    )

@dp.message_handler(commands=['add'])
async def note_add(message: types.Message):
    await NoteStates.waiting_for_note.set()
    await message.reply("Please send me the note text.")

@dp.message_handler(state=NoteStates.waiting_for_note, content_types=types.ContentTypes.TEXT)
async def note_add_text(message: types.Message, state: FSMContext):
    note_text = message.text.strip()
    max_note_length = 1000

    if not note_text:
        await message.reply("The note is empty. Please send some text.")
        return

    if len(note_text) > max_note_length:
        await message.reply(f"The note is too long. Please limit it to {max_note_length} characters.")
        return

    user_id = message.from_user.id
    notes_collection.insert_one({"user_id": user_id, "note": note_text})
    await message.reply("Note added successfully!", reply_markup=get_base_keyboard())
    await state.finish()

@dp.message_handler(commands=['notes'])
async def note_list(message: types.Message):
    user_id = message.from_user.id
    notes = list(notes_collection.find({"user_id": user_id}, {"_id": 0, "note": 1}))

    if not notes:
        await message.reply("You have no notes.")
    else:
        reply = "Your notes:\n"
        for idx, note in enumerate(notes, start=1):
            reply += f"{idx}: {note['note']}\n"
        await message.reply(reply, reply_markup=get_base_keyboard())

@dp.message_handler(commands=['delete'])
async def note_delete(message: types.Message):
    user_id = message.from_user.id
    notes = list(notes_collection.find({"user_id": user_id}, {"_id": 1, "note": 1}))

    if not notes:
        await message.reply("You have no notes.")
        return

    reply = "Select a note to delete. Send the number of the note:\n"
    for idx, note in enumerate(notes, start=1):
        reply += f"{idx}: {note['note']}\n"
    await message.reply(reply, reply_markup=get_base_keyboard())
    await NoteStates.waiting_for_delete_choice.set()

@dp.message_handler(state=NoteStates.waiting_for_delete_choice, content_types=types.ContentTypes.TEXT)
async def delete_selected_note(message: types.Message, state: Dispatcher):
    try:
        user_id = message.from_user.id
        choice = int(message.text.strip()) - 1
        notes = list(notes_collection.find({"user_id": user_id}, {"_id": 1}))

        if choice < 0 or choice >= len(notes):
            await message.reply("Invalid choice. Please try again.")
            return

        notes_collection.delete_one({"_id": notes[choice]["_id"]})
        await message.reply("Note deleted successfully.", reply_markup=get_base_keyboard())
    except ValueError:
        await message.reply("Please send a valid number.")
    except Exception as e:
        logging.error(f"Error deleting note: {e}")
        await message.reply("An error occurred while deleting your note.")
    finally:
        await state.finish()

async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    logging.warning('Shutting down..')
    await bot.delete_webhook()

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )

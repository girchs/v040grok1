import logging
import os
import random
import json
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

SONGS_FOLDER = "songs"
SESSIONS_FOLDER = "user_sessions"

os.makedirs(SONGS_FOLDER, exist_ok=True)
os.makedirs(SESSIONS_FOLDER, exist_ok=True)

# Globālie mainīgie radio stāvokļa pārvaldībai
radio_active = {}  # {group_id: bool} – vai radio ir aktīvs grupā
radio_message = {}  # {group_id: message_id} – pēdējās dziesmas ziņojuma ID

def get_keyboard(radio_mode=False):
    kb = InlineKeyboardMarkup()
    if radio_mode:
        kb.add(
            InlineKeyboardButton("▶️ Play Next Automatically", callback_data="next_auto"),
            InlineKeyboardButton("📜 Playlist", callback_data="show_playlist")
        )
    else:
        kb.add(
            InlineKeyboardButton("▶️ Next", callback_data="next"),
            InlineKeyboardButton("📜 Playlist", callback_data="show_playlist")
        )
    return kb

def get_session_path(user_id):
    return os.path.join(SESSIONS_FOLDER, f"{user_id}.json")

def save_user_session(user_id, group_id):
    with open(get_session_path(user_id), "w") as f:
        json.dump({"group_id": group_id}, f)

def load_user_session(user_id):
    path = get_session_path(user_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("group_id")
    return None

def extract_metadata(file_path, fallback_title):
    try:
        audio = MP3(file_path, ID3=EasyID3)
        title = audio.get("title", [fallback_title])[0]
        artist = audio.get("artist", ["$SQUONK"])[0]
    except Exception:
        title, artist = fallback_title, "$SQUONK"
    return title, artist

async def generate_playlist(chat_id):
    group_id = str(chat_id)
    folder = os.path.join(SONGS_FOLDER, group_id)
    if not os.path.exists(folder):
        return "❌ No songs found.", None

    songs = [f for f in os.listdir(folder) if f.endswith(".mp3")]
    if not songs:
        return "❌ Playlist is empty.", None

    kb = InlineKeyboardMarkup(row_width=1)
    text = "🎵 Playlist:\n"
    for f in songs:
        meta_path = os.path.join(folder, f + ".json")
        title = os.path.splitext(f)[0]
        if os.path.exists(meta_path):
            with open(meta_path) as meta:
                m = json.load(meta)
                title = m.get("title", title)
        text += f"• {title}\n"
        kb.add(InlineKeyboardButton(f"▶️ {title}", callback_data=f"play:{f}"))
    return text, kb

async def play_song(chat_id, song_file=None, radio_mode=False):
    group_id = str(chat_id)
    folder = os.path.join(SONGS_FOLDER, group_id)
    songs = [f for f in os.listdir(folder) if f.endswith(".mp3")]
    if not songs:
        return None, None

    chosen = song_file if song_file else random.choice(songs)
    base = os.path.splitext(chosen)[0]
    meta_path = os.path.join(folder, chosen + ".json")
    file_path = os.path.join(folder, chosen)
    title, artist = base, "$SQUONK"
    duration = int(MP3(file_path).info.length)
    duration_str = f"{duration // 60}:{duration % 60:02d}"
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
            title = meta.get("title", base)
            artist = meta.get("artist", "$SQUONK")

    message = await bot.send_audio(
        chat_id,
        open(file_path, "rb"),
        title=title,
        performer=artist,
        duration=duration,
        caption=(
            f"🎶 Squonking time! 0:00 / {duration_str}\n"
            "Press the Play button above to listen! 🎵\n"
            "Powered by $SQUONK – Learn more at [squonk.meme](https://squonk.meme)\n"
            "💰 Check $SQUONK stats on [Dexscreener](https://dexscreener.com/solana/8MBLr5THhfHevaRNrpij47uvjtRVpw4NeviM6dkt2afy)"
        ),
        reply_markup=get_keyboard(radio_mode=radio_mode)
    )
    return message, duration

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply(
        "👋 Welcome to Squonk Radio V0.4.0!\n"
        "Use /setup in private chat or /play in group.\n"
        "Start the radio with /start_radio and stop with /stop_radio.\n"
        "Note: Press the Play button on each track to listen! 🎵"
    )

@dp.message_handler(commands=["setup"])
async def setup(message: types.Message):
    if message.chat.type != "private":
        return await message.reply("❗ Please use /setup in a private chat.")
    await message.reply("📥 Send me `GroupID: <your_group_id>` first, then upload .mp3 files.")

@dp.message_handler(lambda msg: msg.text and msg.text.startswith("GroupID:"))
async def receive_group_id(message: types.Message):
    group_id = message.text.replace("GroupID:", "").strip()
    if not group_id.lstrip("-").isdigit():
        return await message.reply("❌ Invalid group ID format. Use `GroupID: 123456789`")
    save_user_session(message.from_user.id, group_id)
    await message.reply(f"✅ Group ID `{group_id}` saved. Now send me .mp3 files!")

@dp.message_handler(content_types=types.ContentType.AUDIO)
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    group_id = load_user_session(user_id)
    if not group_id:
        return await message.reply("❗ Please first send `GroupID: <your_group_id>` in this private chat.")

    group_folder = os.path.join(SONGS_FOLDER, group_id)
    os.makedirs(group_folder, exist_ok=True)

    song_id = message.audio.file_unique_id
    file_path = os.path.join(group_folder, f"{song_id}.mp3")
    await message.audio.download(destination_file=file_path)

    fallback_title = os.path.splitext(message.audio.file_name or "Unknown")[0]
    title, artist = extract_metadata(file_path, fallback_title)

    with open(file_path + ".json", "w") as f:
        json.dump({"file": file_path, "title": title, "artist": artist}, f)

    await message.reply(f"✅ Saved `{title}` for group {group_id}")

@dp.message_handler(commands=["play"])
async def play(message: types.Message):
    group_id = str(message.chat.id)
    folder = os.path.join(SONGS_FOLDER, group_id)
    if not os.path.exists(folder):
        return await message.reply("❌ No songs found for this group.")
    songs = [f for f in os.listdir(folder) if f.endswith(".mp3")]
    if not songs:
        return await message.reply("❌ No audio files found.")

    message, duration = await play_song(message.chat.id)
    if message:
        radio_message[group_id] = message.message_id

@dp.message_handler(commands=["start_radio"])
async def start_radio(message: types.Message):
    group_id = str(message.chat.id)
    if radio_active.get(group_id, False):
        return await message.reply("📻 Radio mode is already active! Use /stop_radio to stop.")
    
    radio_active[group_id] = True
    await message.reply(
        "📻 Starting Squonk Radio Mode! 🎵\n"
        "Each track will load automatically. Press the Play button on each track to listen.\n"
        "Use /stop_radio to stop the radio."
    )
    message, duration = await play_song(message.chat.id, radio_mode=True)
    if message:
        radio_message[group_id] = message.message_id

@dp.message_handler(commands=["stop_radio"])
async def stop_radio(message: types.Message):
    group_id = str(message.chat.id)
    if not radio_active.get(group_id, False):
        return await message.reply("📻 Radio mode is not active!")
    
    radio_active[group_id] = False
    if group_id in radio_message:
        await bot.delete_message(chat_id=message.chat.id, message_id=radio_message[group_id])
        del radio_message[group_id]
    await message.reply("📻 Squonk Radio Mode stopped.")

@dp.message_handler(commands=["playlist"])
async def playlist(message: types.Message):
    text, kb = await generate_playlist(message.chat.id)
    await message.reply(text, reply_markup=kb)

@dp.message_handler(commands=["token"])
async def token_info(message: types.Message):
    await message.reply(
        "💰 **$SQUONK Token Info**\n"
        "The heart of the Squonk ecosystem! $SQUONK powers our community and radio bot.\n"
        "🌐 Learn more at [squonk.meme](https://squonk.meme)\n"
        "📊 Check $SQUONK price and stats on [Dexscreener](https://dexscreener.com/solana/8MBLr5THhfHevaRNrpij47uvjtRVpw4NeviM6dkt2afy)\n"
        "Join the squonking revolution! 🚀"
    )

@dp.callback_query_handler(lambda c: c.data.startswith("play:"))
async def callback_play_specific(call: types.CallbackQuery):
    group_id = str(call.message.chat.id)
    song_file = call.data.split(":", 1)[1]
    message, duration = await play_song(call.message.chat.id, song_file, radio_mode=radio_active.get(group_id, False))
    if message:
        radio_message[group_id] = message.message_id
    await call.answer()

@dp.callback_query_handler(lambda c: c.data in ["next", "next_auto", "show_playlist"])
async def callback_buttons(call: types.CallbackQuery):
    group_id = str(call.message.chat.id)
    folder = os.path.join(SONGS_FOLDER, group_id)
    songs = [f for f in os.listdir(folder) if f.endswith(".mp3")]
    if not songs:
        return await call.answer("❌ No songs available.", show_alert=True)

    if call.data in ["next", "next_auto"]:
        message, duration = await play_song(call.message.chat.id, radio_mode=radio_active.get(group_id, False))
        if message:
            radio_message[group_id] = message.message_id
    elif call.data == "show_playlist":
        text, kb = await generate_playlist(call.message.chat.id)
        await call.message.reply(text, reply_markup=kb)

    await call.answer()

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

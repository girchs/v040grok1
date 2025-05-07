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

# Globālie mainīgie atskaņotāja stāvokļa pārvaldībai
player_active = {}  # {group_id: bool} – vai atskaņotājs ir aktīvs grupā
player_message = {}  # {group_id: message_id} – pēdējās dziesmas ziņojuma ID

# Meme teksti par kriptopasauli un mūziku
meme_texts = [
    "HODL the beat, not just the coin! 🎧",
    "This track pumps harder than a bull run! 📈",
    "Crypto vibes only – no fiat tunes here! 💸",
    "To the moon, and to the dance floor! 🌙",
    "Play this while you stake your $SQUONK! 🤑",
    "When the beat drops, so does the market! 📉",
    "Squonking my way to financial freedom! 🚀",
    "This song’s a better investment than my altcoins! 🎶",
    "Turn up the volume, turn down the FUD! 🔊",
    "Crypto whales love this beat – guaranteed! 🐳",
    "Wen lambo? Wen this track ends! 🏎️",
    "This tune’s got more energy than a gas fee! ⛽",
    "Squonk hard, trade smart! 💡",
    "When your portfolio dips, but the beat don’t! 📊",
    "This track’s a 100x gem – don’t miss out! 💎",
    "Rugpulls can’t stop this rhythm! 🕺",
    "Play this while you DCA your $SQUONK! 📅",
    "Mooning to this beat – who needs charts? 🌕",
    "When the market crashes, but the music slaps! 💥",
    "This song’s my new wallet seed phrase! 🔑",
    "Squonking through the bear market like… 🐻",
    "Crypto bros and sick beats – name a better duo! 👊",
    "This track’s hotter than a Solana transaction! ⚡",
    "When your $SQUONK bags are heavy, but the beat is light! 🎒",
    "Don’t FOMO on this song – it’s a banger! 🚨",
    "This tune’s got more pumps than a shitcoin! 📈",
    "Squonk now, panic sell later! 😅",
    "When the beat hits harder than a market dip! 📉",
    "This track’s my exit liquidity – I’m out! 🏃",
    "Play this while you shill $SQUONK to your friends! 🗣️",
    "Crypto gains and music pains – let’s roll! 🎸",
    "When the market’s red, but the vibes are green! 🟢",
    "This song’s a better store of value than BTC! 🪙",
    "Squonking my way to the next ATH! 📈",
    "Who needs a whitepaper when you’ve got this beat? 📜",
    "This track’s my new crypto strategy – vibe only! 🧠",
    "When the beat’s so good, you forget about your losses! 🥳",
    "Squonk hard or go home – no paper hands here! ✋",
    "This song’s my new staking reward! 🎁",
    "When the market’s down, but the music’s up! 🔊",
    "This track’s more decentralized than DeFi! 🌐",
    "Squonking through the dip – nothing can stop me! 💪",
    "Play this while you wait for the next pump! ⏳",
    "This beat’s got more utility than my altcoins! 🔧",
    "When your $SQUONK bags moon, but the beat moons harder! 🌑",
    "Crypto life, music vibes – the perfect combo! 🎤",
    "This track’s my new crypto advisor – trust me! 🤝",
    "Squonk now, DYOR later! 🕵️",
    "When the beat’s so good, you forget about gas fees! ⛽",
    "This song’s my new rugpull protection! 🛡️",
    "Squonking all the way to the bank! 🏦",
    "Play this while you dream of $SQUONK millions! 💭",
    "This track’s the only thing I’m not selling! 🚫",
    "When the market’s volatile, but the beat’s stable! ⚖️"
]

def get_keyboard(player_mode=False):
    kb = InlineKeyboardMarkup()
    if player_mode:
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

async def play_song(chat_id, song_file=None, player_mode=False):
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
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
            title = meta.get("title", base)
            artist = meta.get("artist", "$SQUONK")

    # Izvēlamies nejaušu meme tekstu
    meme_text = random.choice(meme_texts)

    message = await bot.send_audio(
        chat_id,
        open(file_path, "rb"),
        title=title,
        performer=artist,
        duration=duration,
        caption=(
            "Press the Play button above to listen! 🎵\n"
            f"\n"
            f"{meme_text}\n"
            "Powered by $SQUONK – Learn more at squonk.meme"
        ),
        reply_markup=get_keyboard(player_mode=player_mode)
    )
    return message, duration

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply(
        "🎵 **Get Ready to Squonk with $SQUONK Music Player V1!** 🎶\n"
        "Hey there, Squonker! Welcome to the ultimate music experience for the $SQUONK community! 🚀\n\n"
        "🔥 **What’s this all about?**\n"
        "We’re here to bring you the squonkiest beats while celebrating the $SQUONK token. Play tracks, vibe with friends, and dive into the world of $SQUONK – all in one place!\n\n"
        "🎸 **How to Squonk:**\n"
        "- Use /play to spin a single track.\n"
        "- Fire up /start_player for non-stop squonking (stop it with /stop_player).\n"
        "- Check out all tracks with /playlist.\n"
        "- Learn more about $SQUONK with /token.\n"
        "💡 *Tip:* Press the Play button on each track to listen!\n\n"
        "🌟 **Powered by $SQUONK**\n"
        "This player is brought to you by the $SQUONK token – the heart of our ecosystem. Want to know more? Visit squonk.meme and join the squonking revolution!\n\n"
        "Let’s make some noise together! 🎤 #SquonkMusic #SQUONK"
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
        player_message[group_id] = message.message_id

@dp.message_handler(commands=["start_player"])
async def start_player(message: types.Message):
    group_id = str(message.chat.id)
    if player_active.get(group_id, False):
        return await message.reply("🎵 Music player is already active! Use /stop_player to stop.")
    
    player_active[group_id] = True
    await message.reply(
        "🎵 Starting Squonk Music Player! 🎶\n"
        "Each track will load automatically. Press the Play button on each track to listen.\n"
        "Use /stop_player to stop the player."
    )
    message, duration = await play_song(message.chat.id, player_mode=True)
    if message:
        player_message[group_id] = message.message_id

@dp.message_handler(commands=["stop_player"])
async def stop_player(message: types.Message):
    group_id = str(message.chat.id)
    if not player_active.get(group_id, False):
        return await message.reply("🎵 Music player is not active!")
    
    player_active[group_id] = False
    if group_id in player_message:
        await bot.delete_message(chat_id=message.chat.id, message_id=player_message[group_id])
        del player_message[group_id]
    await message.reply("🎵 Squonk Music Player stopped.")

@dp.message_handler(commands=["playlist"])
async def playlist(message: types.Message):
    text, kb = await generate_playlist(message.chat.id)
    await message.reply(text, reply_markup=kb)

@dp.message_handler(commands=["token"])
async def token_info(message: types.Message):
    await message.reply(
        "💰 **$SQUONK Token Info**\n"
        "The heart of the Squonk ecosystem! $SQUONK powers our community and music player.\n"
        "🌐 Learn more at squonk.meme\n"
        "Join the squonking revolution! 🚀"
    )

@dp.callback_query_handler(lambda c: c.data.startswith("play:"))
async def callback_play_specific(call: types.CallbackQuery):
    group_id = str(call.message.chat.id)
    song_file = call.data.split(":", 1)[1]
    message, duration = await play_song(call.message.chat.id, song_file, player_mode=player_active.get(group_id, False))
    if message:
        player_message[group_id] = message.message_id
    await call.answer()

@dp.callback_query_handler(lambda c: c.data in ["next", "next_auto", "show_playlist"])
async def callback_buttons(call: types.CallbackQuery):
    group_id = str(call.message.chat.id)
    folder = os.path.join(SONGS_FOLDER, group_id)
    songs = [f for f in os.listdir(folder) if f.endswith(".mp3")]
    if not songs:
        return await call.answer("❌ No songs available.", show_alert=True)

    if call.data in ["next", "next_auto"]:
        message, duration = await play_song(call.message.chat.id, player_mode=player_active.get(group_id, False))
        if message:
            player_message[group_id] = message.message_id
    elif call.data == "show_playlist":
        text, kb = await generate_playlist(call.message.chat.id)
        await call.message.reply(text, reply_markup=kb)

    await call.answer()

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

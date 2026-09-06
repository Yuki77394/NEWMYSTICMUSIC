import re
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

API_ID = int(getenv("API_ID"))
API_HASH = getenv("API_HASH")

BOT_TOKEN = getenv("BOT_TOKEN")
OWNER_USERNAME = getenv("OWNER_USERNAME","NoMoreLove")
BOT_USERNAME = getenv("BOT_USERNAME" , "DeluluXmusicbot")
BOT_NAME = getenv("BOT_NAME" , "𝑴𝒚𝒔𝒕𝒊𝒄𝒂𝒍 𝑴𝒖𝒔𝒊𝒄 𝑩𝒐𝒕")
ASSUSERNAME = getenv("ASSUSERNAME" , "DeluluXAssistant")
MONGO_DB_URI = getenv("MONGO_DB_URI", None)
DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 17000))
LOGGER_ID = int(getenv("LOGGER_ID", 0))
OWNER_ID = int(getenv("OWNER_ID", 7959152119))
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
HEROKU_API_KEY = getenv("HEROKU_API_KEY")
UPSTREAM_REPO = getenv("UPSTREAM_REPO", "https://github.com/Yuki77394/MystMusic",)
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "main")
GIT_TOKEN = getenv("GIT_TOKEN", None)

# YouTube backend for song search / metadata / download (new API; used by platforms/Youtube.py + utils/autoplay.py + utils/thumbnails.py + core/prewarm.py).
# Read directly from env by Youtube.py / autoplay.py / prewarm.py so Heroku config-var changes take effect on next restart without a redeploy.
API_URL = getenv("API_URL", "http://yt.riteshyt.in")
API_KEY = getenv("API_KEY", "riteshfree576fd88ed84a3f46c84fd556")
YOUTUBE_API_URL = API_URL
YOUTUBE_API_KEY = API_KEY

# Legacy xBit endpoint kept for backward compatibility (not used by the new YouTube platform code).
YTPROXY_URL = getenv("YTPROXY_URL", 'https://tgapi.xbitcode.com') ## xBit Music Endpoint.
YT_API_KEY = getenv("YT_API_KEY" , None ) ## Your API key like: xbit_10000000xx0233 Get from  https://t.me/tgmusic_apibot

PRIVACY_LINK = getenv("PRIVACY_LINK", "")
SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/SpicyxNetwork")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/+gXCu09qmgwA0NjA9")

# ---------------------------------------------------------------------------
# Central Music Archive (OPTIONAL — completely isolated from the existing
# bot MongoDB). When enabled, every successfully downloaded YouTube AUDIO
# track (MP3) is silently archived in the background to:
#   1. A Telegram storage channel (STORAGE_CHANNEL_ID)
#   2. A separate central MongoDB (CENTRAL_MONGO_DB_URI) — uses its own
#      database (CENTRAL_MUSIC_ARCHIVE_DB, default: music_archive) so it
#      NEVER mixes with the existing bot's collections.
# All three values must be set for archival to be active. If any is
# missing, the archive is silently disabled and the bot runs exactly as
# before. Video / MP4 is NEVER archived — audio only.
# ---------------------------------------------------------------------------
CENTRAL_MUSIC_ARCHIVE_ENABLED = (
    (getenv("CENTRAL_MUSIC_ARCHIVE_ENABLED", "false") or "false")
    .strip()
    .lower()
    in ("true", "1", "yes", "on")
)
CENTRAL_MONGO_DB_URI = getenv("CENTRAL_MONGO_DB_URI") or None
CENTRAL_MUSIC_ARCHIVE_DB = (
    getenv("CENTRAL_MUSIC_ARCHIVE_DB", "music_archive") or "music_archive"
)
CENTRAL_MUSIC_ARCHIVE_COLL = (
    getenv("CENTRAL_MUSIC_ARCHIVE_COLL", "tracks") or "tracks"
)
CENTRAL_ARCHIVE_SOURCE_BOT = (
    getenv("CENTRAL_ARCHIVE_SOURCE_BOT", "MystMusic") or "MystMusic"
)
_storage_channel_raw = (getenv("STORAGE_CHANNEL_ID", "") or "").strip()
if _storage_channel_raw:
    try:
        STORAGE_CHANNEL_ID = int(_storage_channel_raw)
    except ValueError:
        # Allow @username form as a fallback.
        STORAGE_CHANNEL_ID = _storage_channel_raw
else:
    STORAGE_CHANNEL_ID = None
AUTO_LEAVING_ASSISTANT = getenv("AUTO_LEAVING_ASSISTANT", "False")
AUTO_LEAVE_ASSISTANT_TIME = int(getenv("ASSISTANT_LEAVE_TIME", "9000"))
SONG_DOWNLOAD_DURATION = int(getenv("SONG_DOWNLOAD_DURATION", "9999999"))
SONG_DOWNLOAD_DURATION_LIMIT = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "9999999"))
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "1c21247d714244ddbb09925dac565aed")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "709e1a2969664491b58200860623ef19")
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", 25))
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", "5242880000"))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", "5242880000"))
STRING1 = getenv("STRING_SESSION", None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)
STRING6 = getenv("STRING_SESSION6", None)
STRING7 = getenv("STRING_SESSION7", None)
BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}
START_IMG_URL = getenv("START_IMG_URL", "https://litter.catbox.moe/xr9jf82b2umeke7j.jpg")
PING_IMG_URL = getenv("PING_IMG_URL", "https://litter.catbox.moe/xyedznhk80hmial2.mp4")
PLAYLIST_IMG_URL = "https://litter.catbox.moe/o91jli53b2qn87v4.jpg"
STATS_IMG_URL = "https://litter.catbox.moe/mzciup11cxe1d6wt.jpg"
TELEGRAM_AUDIO_URL = "https://litter.catbox.moe/7x4b2jc2e6pz6pky.jpg"
TELEGRAM_VIDEO_URL = "https://litter.catbox.moe/7x4b2jc2e6pz6pky.jpg"
STREAM_IMG_URL = "https://telegra.ph/file/d30d11c4365c025c25e3e.jpg"
SOUNCLOUD_IMG_URL = "https://telegra.ph/file/d30d11c4365c025c25e3e.jpg"
YOUTUBE_IMG_URL = "https://files.catbox.moe/2y5o3g.jpg"
SPOTIFY_ARTIST_IMG_URL = "https://files.catbox.moe/2y5o3g.jpg"
SPOTIFY_ALBUM_IMG_URL = "https://files.catbox.moe/2y5o3g.jpg"
SPOTIFY_PLAYLIST_IMG_URL = "https://telegra.ph/file/d30d11c4365c025c25e3e.jpg"
def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))
DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))
if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHANNEL url is wrong. Please ensure that it starts with https://"
        )

if SUPPORT_CHAT:
    if not re.match("(?:http|https)://", SUPPORT_CHAT):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHAT url is wrong. Please ensure that it starts with https://"
        )

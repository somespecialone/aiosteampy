import os
import base64

# env variables
# required
# TEST_USERNAME
# TEST_PASSWORD
# TEST_STEAMID
# TEST_SHARED_SECRET
# TEST_IDENTITY_SECRET

# optional
# TEST_GAME_APP_ID
# TEST_GAME_CONTEXT_ID
# TEST_ASSET_ID
# TEST_COOKIE_FILE_PATH

TEST_COOKIE_FILE_PATH = os.getenv("TEST_COOKIE_FILE_PATH", "")

CREDENTIALS = {
    "username": os.getenv("TEST_USERNAME", ""),
    "password": os.getenv("TEST_PASSWORD", ""),
    "steam_id": int(os.getenv("TEST_STEAMID", 0)),
    "shared_secret": os.getenv("TEST_SHARED_SECRET", ""),
    "identity_secret": os.getenv("TEST_IDENTITY_SECRET", ""),
}

GAME = (int(os.getenv("TEST_GAME_APP_ID", 730)), int(os.getenv("TEST_GAME_CONTEXT_ID", 2)))  # def CSGO
ASSET_ID = int(os.getenv("TEST_ASSET_ID", 0))

UA = "Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36"

MOCK_SHARED_SECRET = base64.b64encode("1234567890abcdefghij".encode("utf-8"))
MOCK_IDENTITY_SECRET = base64.b64encode("abcdefghijklmnoprstu".encode("utf-8"))

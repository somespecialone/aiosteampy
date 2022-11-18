import os
import base64

# env variables
# TEST_USERNAME
# TEST_PASSWORD
# TEST_STEAMID
# TEST_SHARED_SECRET
# TEST_IDENTITY_SECRET

CREDENTIALS = {
    "username": os.getenv("TEST_USERNAME", None),
    "password": os.getenv("TEST_PASSWORD", None),
    "steam_id": int(os.getenv("TEST_STEAMID", 0)),
    "shared_secret": os.getenv("TEST_SHARED_SECRET", None),
    "identity_secret": os.getenv("TEST_IDENTITY_SECRET", None),
}

UA = "Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36"

MOCK_SHARED_SECRET = base64.b64encode("1234567890abcdefghij".encode("utf-8"))
MOCK_IDENTITY_SECRET = base64.b64encode("abcdefghijklmnoprstu".encode("utf-8"))

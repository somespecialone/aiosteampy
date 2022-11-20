from aiosteampy.utils import generate_confirmation_key, gen_two_factor_code, generate_device_id

from data import MOCK_IDENTITY_SECRET, MOCK_SHARED_SECRET


def test_one_time_code():
    ts = 1469184207
    code = gen_two_factor_code(MOCK_SHARED_SECRET, ts)
    assert code == "P2QJN"


def test_confirmation_key():
    ts = 1470838334
    c_key = generate_confirmation_key(MOCK_IDENTITY_SECRET, "conf", ts)
    assert c_key == "pWqjnkcwqni+t/n+5xXaEa0SGeA="


def test_generate_device_id():
    steam_id = 12341234123412345
    device_id = generate_device_id(steam_id)
    assert device_id == "android:677cf5aa-3300-7807-d1e2-c408142742e2"

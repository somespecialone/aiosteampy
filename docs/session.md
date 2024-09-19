## General 

To keep **client** `session` (cookies) across program/script runs, generally between process execution,
we can use utils functions from `utils` modul:

- _get_jsonable_cookies_ - get cookies from `session` in format ready to be json serialized
- _update_session_cookies_ - update `session` with cookies from previously mentioned format

Non-real example, just for understanding:

```python
from aiosteampy import SteamClient
from aiosteampy.utils import get_jsonable_cookies, update_session_cookies

client0 = SteamClient(...)
await client0.login()

### do some client0 work: get inventory, market, etc...

cookies = get_jsonable_cookies(client0.session)
await client0.session.close()  # close client session

# create new client
client1 = SteamClient(...)

# update cookies from client0 to client1
update_session_cookies(client1.session, cookies)

# check if session is alive and do login if it is not
is_alive = await client1.is_session_alive()
if not is_alive:
    await client1.login()

# do another work with client1
```

## Restore

There is a helper function `restore_from_cookies` in `helpers` module to reduce boilerplate code.
What it does is update **client** with passed cookies and try to restore login state: check if session is alive
and do login if it is not:

```python
from aiosteampy import SteamClient
from aiosteampy.utils import get_jsonable_cookies
from aiosteampy.helpers import restore_from_cookies

client0 = SteamClient(...)

### do some client0 work: login, get inventory, etc...
cookies = get_jsonable_cookies(client0.session)
await client0.session.close()  # close client session

# create new client
client1 = SteamClient(...)

# update cookies from client0 to client1
await restore_from_cookies(cookies, client1)

# do another work with client1
```

!!! info "Example"
    See how to handle cookies and store it in `json` file in [example](./examples/session.md)

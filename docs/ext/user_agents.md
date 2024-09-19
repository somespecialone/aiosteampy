# User Agents Service 🕶️

`List-like` class of user agents responsible for loading and getting random user agents.

!!! note ""
    Instance is an API consumer of [Random User Agent](https://github.com/somespecialone/random-user-agent).

## Creating instance and loading agents

```python
from aiosteampy.ext.user_agents import UserAgentsService

user_agents = UserAgentsService()
await user_agents.load()
```

## Getting random

```python
random_user_agent = user_agents.get_random()
```

## List behaviour

Since the class inherits `collections.UserList`, it implements `list` methods,
which means you can do the following:

```python
for agent in user_agents:  # iterate over
    print(agent)

len(user_agents)  # know agents count
user_agents.append("user_agent")  # append
user_agents.remove("user-agent")  # and even remove
```

Let's talk about `App` and `AppContext` enum's a little. 

Thankfully to an [aenum](https://github.com/ethanfurman/aenum) package, these enum's extending selves when member is
missing. Therefore, as mentioned before, hardcoded members are just _predefined_.

!!! note ""
    You can create `App` and `AppContext` for non-predefined app+context

As instance:

```python
from aiosteampy import App, AppContext

BANANA_APP = App(2923300)
BANANA = AppContext((BANANA_APP, 2))  # with context 2
```

And then use it within your app. Moreover, from now `AppContext` and `App` enums have a new member.

### Caveat

If you print/log `BANANA_APP` you receive something like 

```sh
<AppContext.AppContext_2923300_2: (<App.App_2923300: 2923300>, 2)>
```

Not so beautiful, yes. Name is auto-generated, due to inability to know name of the app, if we, for example, 
get a `trade offer` with non-predefined app items.

!!! warning "Next version"
    Solution comes in next minor version (0.6.4)

As a workaround you can extend enum manually:

```python
from aenum import extend_enum
from aiosteampy import App, AppContext

BANANA_APP = extend_enum(App, "BANANA", 2923300)
BANANA_DEFAULT_CONTEXT = extend_enum(
    AppContext, 
    "BANANA_DEFAULT_CONTEXT", 
    (BANANA_APP, 2),
)  # with context 2
```

Then `repr` of a `AppContext` new member will be:
```sh
<AppContext.BANANA_DEFAULT_CONTEXT: (<App.BANANA: 2923300>, 2)>
```

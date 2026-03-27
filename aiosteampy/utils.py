"""Abstract utils within `Steam` context and not"""

import re
from typing import overload


def extract_openid_payload(page_text: str) -> dict[str, str]:
    """
    Extract steam openid urlencoded (specs) from page html raw text.
    Use it if 3rd party websites have extra or non-cookie auth (JWT via service API call, for ex.).

    :param page_text:
    :return: dict with urlencoded data
    """

    # not so beautiful as with bs4 but dependency free
    return {
        "action": re.search(r"id=\"actionInput\"[\w=\"\s]+value=\"(?P<action>\w+)\"", page_text)["action"],
        "openid.mode": re.search(r"name=\"openid\.mode\"[\w=\"\s]+value=\"(?P<mode>\w+)\"", page_text)["mode"],
        "openidparams": re.search(r"name=\"openidparams\"[\w=\"\s]+value=\"(?P<params>[\w=/]+)\"", page_text)["params"],
        "nonce": re.search(r"name=\"nonce\"[\w=\"\s]+value=\"(?P<nonce>\w+)\"", page_text)["nonce"],
    }


# TODO remove overloading and write examples in docstring: args should be from most narrow to wide (inst, class, app)
@overload
def create_ident_code(asset_id: int | str, context_id: int | str, app_id: int | str, *, sep: str = ...) -> str: ...


@overload
def create_ident_code(instance_id: int | str, class_id: int | str, app_id: int | str, *, sep: str = ...) -> str: ...


def create_ident_code(*args, sep=":"):
    """
    Create unique ident code for ``EconItem`` or ``ItemDescription`` within whole `Steam Economy`.

    .. seealso:: https://dev.doctormckay.com/topic/332-identifying-steam-items/
    """

    return sep.join(reversed(list(str(i) for i in filter(lambda i: i is not None, args))))

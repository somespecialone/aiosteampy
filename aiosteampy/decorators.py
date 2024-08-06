"""Decorators for client/mixins methods"""

from .utils import attribute_required


api_key_required = attribute_required(
    "_api_key",
    "You must provide an API key to client or init data before use this method",
)


wallet_currency_required = attribute_required(
    "_wallet_currency",
    "You must provide wallet currency key to client or init data before use this method",
)

identity_secret_required = attribute_required(
    "_identity_secret",
    "You must provide identity secret to client before use this method",
)

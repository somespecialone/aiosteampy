"""
Manage Steam sessions, Guard, Market, trade offers and more.

Package separated into *main modules* which can be imported from ``aiosteampy`` namespace:

- ``session`` - `Steam Session` management and auth tokens negotiation;
- ``guard`` - `Steam Guard/Mobile Authenticator` (2FA) functionality;
- ``client`` - abstract container for `Steam` domains implementations (`Market`, `Trade Offers`, etc.).
"""

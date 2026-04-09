"""Constants shared across ``Steam Client`` components."""

from enum import IntEnum, StrEnum


class Currency(IntEnum):
    """
    All `Steam` currencies.

    .. seealso::
        Currently supported currencies: https://partner.steamgames.com/doc/store/pricing/currencies.
    """

    USD = 1
    """United States Dollar."""
    GBP = 2
    """United Kingdom Pound."""
    EUR = 3
    """European Union Euro."""
    CHF = 4
    """Swiss Francs."""
    RUB = 5
    """Russian Rouble."""
    PLN = 6
    """Polish Złoty."""
    BRL = 7
    """Brazilian Reals."""
    JPY = 8
    """Japanese Yen."""
    NOK = 9
    """Norwegian Krone."""
    IDR = 10
    """Indonesian Rupiah."""
    MYR = 11
    """Malaysian Ringgit."""
    PHP = 12
    """Philippine Peso."""
    SGD = 13
    """Singapore Dollar."""
    THB = 14
    """Thai Baht."""
    VND = 15
    """Vietnamese Dong."""
    KRW = 16
    """South Korean Won."""
    TRY = 17
    """Turkish Lira. **Support suspended**."""
    UAH = 18
    """Ukrainian Hryvnia."""
    MXN = 19
    """Mexican Peso."""
    CAD = 20
    """Canadian Dollars."""
    AUD = 21
    """Australian Dollars."""
    NZD = 22
    """New Zealand Dollar."""
    CNY = 23
    """Chinese Renminbi (yuan)."""
    INR = 24
    """Indian Rupee."""
    CLP = 25
    """Chilean Peso."""
    PEN = 26
    """Peruvian Sol."""
    COP = 27
    """Colombian Peso."""
    ZAR = 28
    """South African Rand."""
    HKD = 29
    """Hong Kong Dollar."""
    TWD = 30
    """New Taiwan Dollar."""
    SAR = 31
    """Saudi Riyal."""
    AED = 32
    """United Arab Emirates Dirham."""
    SEK = 33
    """Swedish Krona. **Support suspended**."""
    ARS = 34
    """Argentine Peso. **Support suspended**."""
    ILS = 35
    """Israeli New Shekel."""
    BYN = 36
    """Belarusian Ruble. **Support suspended**."""
    KZT = 37
    """Kazakhstani Tenge."""
    KWD = 38
    """Kuwaiti Dinar."""
    QAR = 39
    """Qatari Riyal."""
    CRC = 40
    """Costa Rican Colón."""
    UYU = 41
    """Uruguayan Peso."""
    BGN = 42
    """Bulgarian Lev. **Support suspended**."""
    HRK = 43
    """Croatian Kuna. **Support suspended**."""
    CZK = 44
    """Czech Koruna. **Support suspended**."""
    DKK = 45
    """Danish Krone. **Support suspended**."""
    HUF = 46
    """Hungarian Forint. **Support suspended**."""
    RON = 47
    """Romanian Leu. **Support suspended**."""


class Language(StrEnum):
    """
    Supported languages by `Steam`.

    .. seealso:: https://partner.steamgames.com/doc/store/localization/languages.
    """

    ARABIC = "arabic"
    BULGARIAN = "bulgarian"
    SIMPLIFIED_CHINESE = "schinese"
    TRADITIONAL_CHINESE = "tchinese"
    CZECH = "czech"
    DANISH = "danish"
    DUTCH = "dutch"
    ENGLISH = "english"
    FINNISH = "finnish"
    FRENCH = "french"
    GERMAN = "german"
    GREEK = "greek"
    HUNGARIAN = "hungarian"
    ITALIAN = "italian"
    JAPANESE = "japanese"
    KOREAN = "koreana"
    NORWEGIAN = "norwegian"
    POLISH = "polish"
    PORTUGUESE = "portuguese"
    PORTUGUESE_BRAZIL = "brazilian"
    ROMANIAN = "romanian"
    RUSSIAN = "russian"
    SPANISH = "spanish"
    SPANISH_LATIN_AMERICAN = "latam"
    SWEDISH = "swedish"
    THAI = "thai"
    TURKISH = "turkish"
    UKRAINIAN = "ukrainian"
    VIETNAMESE = "vietnamese"

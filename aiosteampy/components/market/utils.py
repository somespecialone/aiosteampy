from math import floor


def receive_to_buyer_pays(
    amount: int,
    *,
    publisher_fee: float = 0.10,
    steam_fee: float = 0.05,
    wallet_fee_min: float = 1,
    wallet_fee_base: float = 0,
) -> tuple[int, int, int]:
    """
    Convert `to receive` amount to `buyer pays`. Needed for placing sell listing.
    Works like function from sell listing window on `Steam`.

    :param amount: desired `to receive` amount in cents.
    :param publisher_fee: publisher fee value, in percents.
    :param steam_fee: `Steam` fee value, in percents.
    :param wallet_fee_min: wallet minimum fee value, in cents.
    :param wallet_fee_base: wallet base fee value, in cents.
    :return: `Steam` fee value, publisher fee value, buyer pays amount.
    """

    steam_fee_value = int(floor(max(amount * steam_fee, wallet_fee_min) + wallet_fee_base))
    publisher_fee_value = int(floor(max(amount * publisher_fee, 1) if publisher_fee > 0 else 0))
    return steam_fee_value, publisher_fee_value, int(amount + steam_fee_value + publisher_fee_value)


def buyer_pays_to_receive(
    amount: int,
    *,
    publisher_fee: float = 0.10,
    steam_fee: float = 0.05,
    wallet_fee_min: float = 1,
    wallet_fee_base: float = 0,
) -> tuple[int, int, int]:
    """
    Convert `buyer pays` amount to `to receive`. Needed for placing sell listing.
    Works like function from sell listing window on `Steam`.

    :param amount: desired amount, that buyer must pay, in cents.
    :param publisher_fee: publisher fee value, in percents.
    :param steam_fee: `Steam` fee value, in percents.
    :param wallet_fee_min: wallet minimum fee value, in cents.
    :param wallet_fee_base: wallet base fee value, in cents.
    :return: `Steam` fee value, publisher fee value, amount to receive.
    """

    # I don't know how it works, it's just a copy of js function working on inputs in steam front
    estimated_amount = int((amount - wallet_fee_base) / (steam_fee + publisher_fee + 1))
    s_fee, p_fee, v = receive_to_buyer_pays(
        estimated_amount,
        publisher_fee=publisher_fee,
        steam_fee=steam_fee,
        wallet_fee_min=wallet_fee_min,
        wallet_fee_base=wallet_fee_base,
    )

    i = 0
    some_flag = False
    while (v != amount) and (i < 10):
        if v > amount:
            if some_flag:
                s_fee, p_fee, v = receive_to_buyer_pays(
                    estimated_amount - 1,
                    publisher_fee=publisher_fee,
                    steam_fee=steam_fee,
                    wallet_fee_min=wallet_fee_min,
                    wallet_fee_base=wallet_fee_base,
                )
                s_fee += amount - v
                v = amount
                break
            else:
                estimated_amount -= 1
        else:
            some_flag = True
            estimated_amount += 1

        s_fee, p_fee, v = receive_to_buyer_pays(
            estimated_amount,
            publisher_fee=publisher_fee,
            steam_fee=steam_fee,
            wallet_fee_min=wallet_fee_min,
            wallet_fee_base=wallet_fee_base,
        )
        i += 1

    return s_fee, p_fee, int(v - s_fee - p_fee)


def calc_market_listing_fee(price: int, *, wallet_fee=0.05, publisher_fee=0.10, minimal_fee=1) -> int:
    """
    Calculate total market fee for listing.

    :param price: price of market listing without fee ala `subtotal` in cents.
    :param wallet_fee: `Steam` fee.
    :param publisher_fee: app publisher fee.
    :param minimal_fee: minimal fee value in cents.
    :return: calculated fee of price in cents.
    """

    return (floor(price * wallet_fee) or minimal_fee) + (floor(price * publisher_fee) or minimal_fee)

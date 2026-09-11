import os
import re
import requests
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID_RAW = os.getenv("ADMIN_ID")

if not ADMIN_ID_RAW:
    raise RuntimeError(
        "ADMIN_ID environment variable is missing."
    )

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    raise RuntimeError(
        "ADMIN_ID must be a numeric Telegram user ID."
    )

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")


# ============================================================
# API
# ============================================================

DEX_TOKEN_URL = (
    "https://api.dexscreener.com/latest/dex/tokens/"
)

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
)


# ============================================================
# NETWORK WALLETS
# ============================================================

NETWORK_WALLETS = {
    "SOL": os.getenv("SOL_WALLET"),
    "ETH": os.getenv("ETH_WALLET"),
    "BSC": os.getenv("BSC_WALLET"),
    "BASE": os.getenv("BASE_WALLET"),
    "SUI": os.getenv("SUI_WALLET"),
    "XRP": os.getenv("XRP_WALLET"),
}


# ============================================================
# PACKAGES
# ============================================================

PACKAGES = {
    "24H": 2500,
    "48H": 5500,
    "72H": 8000,
    "96H": 10500,
    "120H": 13000,
    "144H": 15500,
    "168H": 18000,
}


# ============================================================
# USER STATE
# ============================================================

USER_STATE = {}

USED_TXIDS = set()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_float(value, default=0.0):
    """
    Safely convert a value to float.

    Prevents crashes when APIs return:
    - None
    - empty strings
    - invalid strings
    - unexpected values
    """

    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_text(value, default="N/A"):
    """
    Safely convert a value to text.
    """

    if value is None:
        return default

    value = str(value).strip()

    if not value:
        return default

    return value


def valid_contract_input(text):
    """
    Basic validation to prevent accidental huge/error messages
    from being sent to DexScreener.

    We intentionally keep this flexible because different
    blockchain networks use different address formats.
    """

    if not text:
        return False

    text = text.strip()

    if len(text) < 10:
        return False

    if len(text) > 200:
        return False

    # Reject obvious multiline/error-log input.
    if "\n" in text or "\r" in text:
        return False

    return True


def answer_callback(query, text=None, show_alert=False):
    """
    Safely answer a Telegram callback query.

    This prevents callback-answer exceptions from breaking
    the rest of the button handler.
    """

    try:
        if text:
            query.answer(
                text=text,
                show_alert=show_alert,
            )
        else:
            query.answer()

    except Exception as e:
        print(f"Callback answer error: {e}")


# ============================================================
# COINGECKO
# ============================================================

def get_price(symbol):

    ids = {
        "SOL": "solana",
        "ETH": "ethereum",
        "BSC": "binancecoin",
        "BASE": "ethereum",
        "SUI": "sui",
        "XRP": "ripple",
    }

    coin_id = ids.get(symbol)

    if not coin_id:
        print(
            f"Unknown network price requested: {symbol}"
        )
        return None

    try:

        response = requests.get(
            COINGECKO_URL,
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
            },
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        price = (
            data
            .get(coin_id, {})
            .get("usd")
        )

        price = safe_float(
            price,
            default=0.0,
        )

        if price <= 0:
            print(
                f"CoinGecko returned invalid price "
                f"for {symbol}: {price}"
            )
            return None

        return price

    except Exception as e:

        print(
            f"CoinGecko error for {symbol}: {e}"
        )

        return None


# ============================================================
# DEXSCREENER
# ============================================================

def fetch_dex_data(contract_address):

    if not valid_contract_input(
        contract_address
    ):
        print(
            "Invalid contract input received."
        )
        return None

    contract_address = contract_address.strip()

    try:

        response = requests.get(
            f"{DEX_TOKEN_URL}{contract_address}",
            timeout=15,
        )

        response.raise_for_status()

        result = response.json()

        pairs = result.get("pairs") or []

    except requests.HTTPError as e:

        print(
            f"DexScreener HTTP error: {e}"
        )

        return None

    except Exception as e:

        print(
            f"DexScreener error: {e}"
        )

        return None

    if not pairs:

        print(
            "DexScreener returned no pairs."
        )

        return None

    # ========================================================
    # SELECT HIGHEST-LIQUIDITY PAIR
    # ========================================================

    pair = max(
        pairs,
        key=lambda p: safe_float(
            (
                p.get("liquidity") or {}
            ).get("usd")
        ),
    )

    # ========================================================
    # LINKS
    # ========================================================

    telegram = None
    twitter = None

    info = pair.get("info") or {}

    links = info.get("links") or []

    for link in links:

        if not isinstance(link, dict):
            continue

        link_type = link.get("type")
        link_url = link.get("url")

        if link_type == "telegram":
            telegram = link_url

        elif link_type == "twitter":
            twitter = link_url

    # ========================================================
    # TOKEN DATA
    # ========================================================

    base_token = pair.get(
        "baseToken"
    ) or {}

    liquidity = pair.get(
        "liquidity"
    ) or {}

    return {
        "name": safe_text(
            base_token.get("name"),
            "Unknown Token",
        ),

        "symbol": safe_text(
            base_token.get("symbol"),
            "UNKNOWN",
        ),

        "price": safe_text(
            pair.get("priceUsd"),
            "N/A",
        ),

        "liquidity": safe_float(
            liquidity.get("usd")
        ),

        "mcap": safe_float(
            pair.get("fdv")
        ),

        "pair_url": safe_text(
            pair.get("url"),
            "",
        ),

        "logo": info.get(
            "imageUrl"
        ),

        "telegram": telegram,

        "twitter": twitter,

        "chain": str(
            pair.get("chainId") or ""
        ).lower(),
    }


# ============================================================
# START
# ============================================================

def start(update: Update, context: CallbackContext):

    keyboard = [
        [
            InlineKeyboardButton(
                "🐰 Activate Weibo Trending 🇨🇳",
                callback_data="START",
            )
        ]
    ]

    update.message.reply_text(
        "🔥 WEIBO TRENDING 🇨🇳 🐇\n\n"
        "🐰 Boost Visibility for your Token "
        "in the Chinese market\n"
        "Fast Activation • Manual Control • "
        "Chinese visibility 🇨🇳",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# ============================================================
# BUTTON HANDLER
# ============================================================

def buttons(
    update: Update,
    context: CallbackContext,
):

    query = update.callback_query

    if not query:
        return

    uid = query.from_user.id

    data = query.data or ""

    state = USER_STATE.get(uid)

    print(
        f"Button pressed: user={uid}, data={data}"
    )

    # ========================================================
    # START
    # ========================================================

    if data == "START":

        answer_callback(query)

        keyboard = [
            [
                InlineKeyboardButton(
                    "SOL",
                    callback_data="NET_SOL",
                ),
                InlineKeyboardButton(
                    "ETH",
                    callback_data="NET_ETH",
                ),
                InlineKeyboardButton(
                    "BSC",
                    callback_data="NET_BSC",
                ),
            ],
            [
                InlineKeyboardButton(
                    "SUI",
                    callback_data="NET_SUI",
                ),
                InlineKeyboardButton(
                    "BASE",
                    callback_data="NET_BASE",
                ),
                InlineKeyboardButton(
                    "XRP",
                    callback_data="NET_XRP",
                ),
            ],
        ]

        try:
            query.message.delete()
        except Exception:
            pass

        try:

            context.bot.send_photo(
                chat_id=uid,
                photo=(
                    "https://raw.githubusercontent.com/"
                    "edenalpha687/weibo-trending-bot/main/"
                    "1190BF8B-063E-4AFE-8B1D-88E9BF653834.png"
                ),
                caption="Choose Network",
                reply_markup=InlineKeyboardMarkup(
                    keyboard
                ),
            )

        except Exception as e:

            print(
                f"START button error: {e}"
            )

            context.bot.send_message(
                chat_id=uid,
                text="Choose Network",
                reply_markup=InlineKeyboardMarkup(
                    keyboard
                ),
            )

        return

    # ========================================================
    # NETWORK
    # ========================================================

    if data.startswith("NET_"):

        answer_callback(query)

        network = data.replace(
            "NET_",
            "",
            1,
        )

        if network not in NETWORK_WALLETS:

            answer_callback(
                query,
                "Invalid network.",
                True,
            )

            return

        USER_STATE[uid] = {
            "step": "CA",
            "network": network,
        }

        try:
            query.message.delete()
        except Exception:
            pass

        try:

            context.bot.send_photo(
                chat_id=uid,
                photo=(
                    "https://raw.githubusercontent.com/"
                    "edenalpha687/weibo-trending-bot/main/"
                    "F33A4A2F-E8A9-440E-BA47-F7603692010A.png"
                ),
                caption=(
                    f"Enter your {network} "
                    "Token CA"
                ),
            )

        except Exception as e:

            print(
                f"Network button error: {e}"
            )

            context.bot.send_message(
                chat_id=uid,
                text=(
                    f"Enter your {network} "
                    "Token CA"
                ),
            )

        return

    # ========================================================
    # PACKAGES
    # ========================================================

    if data == "PACKAGES":

        if not state:

            answer_callback(
                query,
                "Session expired. Please start again.",
                True,
            )

            return

        answer_callback(query)

        keyboard = [
            [
                InlineKeyboardButton(
                    "24H • $2,500",
                    callback_data="PKG_24H",
                ),
                InlineKeyboardButton(
                    "48H • $5,500",
                    callback_data="PKG_48H",
                ),
            ],
            [
                InlineKeyboardButton(
                    "72H • $8,000",
                    callback_data="PKG_72H",
                ),
                InlineKeyboardButton(
                    "96H • $10,500",
                    callback_data="PKG_96H",
                ),
            ],
            [
                InlineKeyboardButton(
                    "120H • $13,000",
                    callback_data="PKG_120H",
                ),
                InlineKeyboardButton(
                    "144H • $15,500",
                    callback_data="PKG_144H",
                ),
            ],
            [
                InlineKeyboardButton(
                    "168H • $18,000",
                    callback_data="PKG_168H",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="START",
                )
            ],
        ]

        try:

            context.bot.send_message(
                chat_id=uid,
                text=(
                    "🇨🇳 "
                    "<b>Select Trending Duration</b>"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    keyboard
                ),
            )

        except Exception as e:

            print(
                f"Packages button error: {e}"
            )

        return

    # ========================================================
    # PACKAGE SELECTED
    # ========================================================

    if data.startswith("PKG_"):

        if not state:

            answer_callback(
                query,
                "Session expired. Please start again.",
                True,
            )

            return

        pkg = data.replace(
            "PKG_",
            "",
            1,
        )

        if pkg not in PACKAGES:

            answer_callback(
                query,
                "Invalid package.",
                True,
            )

            return

        answer_callback(
            query,
            "Calculating payment amount...",
        )

        state["package"] = pkg

        usd_price = PACKAGES[pkg]

        network = state.get(
            "network"
        )

        coin_price = get_price(
            network
        )

        if not coin_price:

            answer_callback(
                query,
                "Unable to get the current network price. Please try again.",
                True,
            )

            return

        amount = round(
            (usd_price / coin_price) * 1.02,
            4,
        )

        state["amount"] = amount

        # ====================================================
        # TOKEN NAME
        # ====================================================

        link = (
            state.get("telegram")
            or state.get("twitter")
            or state.get("pair_url")
            or ""
        )

        token_name = safe_text(
            state.get("name"),
            "Unknown Token",
        )

        if link:

            name_line = (
                f'<a href="{link}">'
                f'<b>{token_name}</b>'
                f'</a>'
            )

        else:

            name_line = (
                f"<b>{token_name}</b>"
            )

        # ====================================================
        # PRICE
        # ====================================================

        pair_url = (
            state.get("pair_url")
            or ""
        )

        token_price = safe_text(
            state.get("price"),
            "N/A",
        )

        if pair_url:

            price_line = (
                f'💰 <a href="{pair_url}">'
                f"Price: ${token_price}"
                f"</a>"
            )

        else:

            price_line = (
                f"💰 Price: ${token_price}"
            )

        # ====================================================
        # LIQUIDITY + MARKET CAP
        # ====================================================

        liquidity = safe_float(
            state.get("liquidity")
        )

        mcap = safe_float(
            state.get("mcap")
        )

        # ====================================================
        # OVERVIEW
        # ====================================================

        caption = (
            "🚀 <b>Token Overview</b>\n\n"
            f"🐰 {name_line}\n"
            f"🔹 Symbol: "
            f"{safe_text(state.get('symbol'), 'UNKNOWN')}\n"
            f"{price_line}\n"
            f"💧 Liquidity: "
            f"${liquidity:,.2f}\n"
            f"📊 Market Cap: "
            f"${mcap:,.0f}\n\n"
            f"⏱ Package: <b>{pkg}</b>\n"
            f"💎 Pay: "
            f"<b>{amount} {network}</b>"
        )

        try:
            query.message.delete()
        except Exception:
            pass

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Confirm",
                        callback_data="PAY",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="PACKAGES",
                    )
                ],
            ]
        )

        logo = state.get("logo")

        try:

            if logo:

                try:

                    context.bot.send_photo(
                        chat_id=uid,
                        photo=logo,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )

                except Exception as logo_error:

                    print(
                        f"Logo send failed: "
                        f"{logo_error}"
                    )

                    context.bot.send_message(
                        chat_id=uid,
                        text=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )

            else:

                context.bot.send_message(
                    chat_id=uid,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

        except Exception as e:

            print(
                f"Package overview error: {e}"
            )

            try:

                context.bot.send_message(
                    chat_id=uid,
                    text=(
                        "❌ Unable to display "
                        "the token overview. "
                        "Please try again."
                    ),
                )

            except Exception:
                pass

        return

    # ========================================================
    # CONFIRM PAYMENT
    # ========================================================

    if data == "PAY":

        print(
            f"PAY button received "
            f"from user {uid}"
        )

        if not state:

            answer_callback(
                query,
                "Session expired. Please start again.",
                True,
            )

            return

        network = state.get(
            "network"
        )

        if not network:

            answer_callback(
                query,
                "Network information is missing.",
                True,
            )

            return

        wallet = NETWORK_WALLETS.get(
            network
        )

        if not wallet:

            answer_callback(
                query,
                f"{network} payment wallet is not configured.",
                True,
            )

            print(
                f"Missing wallet for {network}"
            )

            return

        package = state.get(
            "package"
        )

        if not package:

            answer_callback(
                query,
                "Package information is missing.",
                True,
            )

            return

        amount = safe_float(
            state.get("amount"),
            default=0.0,
        )

        if amount <= 0:

            answer_callback(
                query,
                "Payment amount is missing.",
                True,
            )

            return

        # ====================================================
        # ACKNOWLEDGE BUTTON
        # ====================================================

        answer_callback(
            query,
            "Preparing payment details...",
        )

        # ====================================================
        # CHANGE USER STATE TO TXID
        # ====================================================

        state["step"] = "TXID"

        # ====================================================
        # PAYMENT MESSAGE
        # ====================================================

        payment_message = (
            "🇨🇳 "
            "<b>Weibo Trending Activation | 激活确认</b>"
            "\n\n"
            f"┃ Network: <b>{network}</b>\n"
            f"┃ Package: <b>{package}</b>\n"
            f"┃ Amount: "
            f"<b>{amount:g} {network}</b>\n\n"
            "──────────────\n"
            "✅ <b>Activation Address</b>\n"
            f"<code>{wallet}</code>\n"
            "──────────────\n\n"
            "💰 Send the exact amount to the "
            "address above.\n\n"
            "🛎️ <b>After payment, send the TXID here.</b>"
        )

        try:

            context.bot.send_message(
                chat_id=uid,
                text=payment_message,
                parse_mode="HTML",
            )

            print(
                f"Payment instructions sent "
                f"to user {uid}"
            )

        except Exception as e:

            print(
                f"PAY send_message error: {e}"
            )

            # Put the user back into the previous
            # state if the payment message failed.
            state["step"] = "CA"

            try:

                answer_callback(
                    query,
                    "Unable to send payment details. Please try again.",
                    True,
                )

            except Exception:
                pass

        return

    # ========================================================
    # ADMIN START TRENDING
    # ========================================================

    if data.startswith("ADMIN_START_"):

        if uid != ADMIN_ID:

            answer_callback(
                query,
                "Unauthorized.",
                True,
            )

            return

        answer_callback(
            query,
            "Activating trending...",
        )

        ref = data.replace(
            "ADMIN_START_",
            "",
            1,
        )

        payload = context.bot_data.pop(
            ref,
            None,
        )

        if not payload:

            answer_callback(
                query,
                "Payment session expired.",
                True,
            )

            return

        if not CHANNEL_USERNAME:

            answer_callback(
                query,
                "CHANNEL_USERNAME is not configured.",
                True,
            )

            return

        try:

            context.bot.send_message(
                chat_id=CHANNEL_USERNAME,
                text=(
                    "🔥 Weibo Trending Live 🇨🇳\n\n"
                    f"{payload.get('name', 'Unknown')} "
                    f"({payload.get('symbol', 'UNKNOWN')})\n"
                    f"CA: {payload.get('ca', 'N/A')}\n"
                    f"Started: "
                    f"{datetime.utcnow().strftime('%H:%M UTC')}"
                ),
            )

            query.edit_message_text(
                "✅ Trending activated."
            )

        except Exception as e:

            print(
                f"Admin activation error: {e}"
            )

            try:

                query.edit_message_text(
                    "❌ Unable to activate trending."
                )

            except Exception:
                pass

        return


# ============================================================
# MESSAGE HANDLER
# ============================================================

def messages(
    update: Update,
    context: CallbackContext,
):

    if not update.message:
        return

    if not update.message.text:
        return

    uid = update.message.from_user.id

    txt = update.message.text.strip()

    state = USER_STATE.get(uid)

    if not state:
        return

    print(
        f"Message from {uid}: "
        f"step={state.get('step')}"
    )

    # ========================================================
    # CONTRACT ADDRESS
    # ========================================================

    if state.get("step") == "CA":

        if not valid_contract_input(txt):

            update.message.reply_text(
                "❌ Invalid contract address.\n\n"
                "Please send the token contract address "
                "only."
            )

            return

        # ====================================================
        # FETCH DEX DATA
        # ====================================================

        data = fetch_dex_data(
            txt
        )

        if not data:

            update.message.reply_text(
                "❌ Token not found or "
                "DexScreener is unavailable.\n\n"
                "Please check the contract address "
                "and try again."
            )

            return

        # ====================================================
        # NETWORK CHECK
        # ====================================================

        chain_map = {
            "SOL": [
                "solana"
            ],

            "ETH": [
                "ethereum",
                "eth",
            ],

            "BSC": [
                "bsc",
                "binance-smart-chain",
            ],

            "BASE": [
                "base",
            ],

            "SUI": [
                "sui",
            ],

            "XRP": [
                "xrpl",
                "xrp",
            ],
        }

        token_chain = (
            data.get("chain")
            or ""
        ).lower()

        selected_network = (
            state.get("network")
            or ""
        )

        allowed_chains = chain_map.get(
            selected_network,
            [],
        )

        if (
            token_chain
            and allowed_chains
            and token_chain not in allowed_chains
        ):

            update.message.reply_text(
                f"❌ Wrong network.\n\n"
                f"You selected "
                f"<b>{selected_network}</b>, "
                f"but the token appears to be "
                f"on <b>{token_chain.upper()}</b>.",
                parse_mode="HTML",
            )

            return

        # ====================================================
        # SAVE TOKEN DATA
        # ====================================================

        state.update(
            data
        )

        state["ca"] = txt

        # ====================================================
        # TOKEN NAME
        # ====================================================

        link = (
            data.get("telegram")
            or data.get("twitter")
            or data.get("pair_url")
            or ""
        )

        token_name = safe_text(
            data.get("name"),
            "Unknown Token",
        )

        if link:

            name_line = (
                f'<a href="{link}">'
                f"<b>{token_name}</b>"
                f"</a>"
            )

        else:

            name_line = (
                f"<b>{token_name}</b>"
            )

        # ====================================================
        # PRICE
        # ====================================================

        pair_url = (
            data.get("pair_url")
            or ""
        )

        token_price = safe_text(
            data.get("price"),
            "N/A",
        )

        if pair_url:

            price_line = (
                f'💰 <a href="{pair_url}">'
                f"Price: ${token_price}"
                f"</a>"
            )

        else:

            price_line = (
                f"💰 Price: ${token_price}"
            )

        # ====================================================
        # MARKET DATA
        # ====================================================

        liquidity = safe_float(
            data.get("liquidity")
        )

        mcap = safe_float(
            data.get("mcap")
        )

        # ====================================================
        # TOKEN OVERVIEW
        # ====================================================

        caption = (
            "🚀 <b>Token Overview</b>\n\n"
            f"🐰 {name_line}\n"
            f"🔹 Symbol: "
            f"{safe_text(data.get('symbol'), 'UNKNOWN')}\n"
            f"{price_line}\n"
            f"💧 Liquidity: "
            f"${liquidity:,.2f}\n"
            f"📊 Market Cap: "
            f"${mcap:,.0f}"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Continue",
                        callback_data="PACKAGES",
                    )
                ]
            ]
        )

        logo = data.get(
            "logo"
        )

        # ====================================================
        # SEND OVERVIEW
        # ====================================================

        try:

            if logo:

                try:

                    context.bot.send_photo(
                        chat_id=uid,
                        photo=logo,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )

                except Exception as logo_error:

                    print(
                        f"Logo error: "
                        f"{logo_error}"
                    )

                    context.bot.send_message(
                        chat_id=uid,
                        text=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )

            else:

                context.bot.send_message(
                    chat_id=uid,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

        except Exception as e:

            print(
                f"Token overview error: {e}"
            )

            try:

                context.bot.send_message(
                    chat_id=uid,
                    text=(
                        "❌ Unable to display "
                        "token information. "
                        "Please try again."
                    ),
                )

            except Exception:
                pass

        return

    # ========================================================
    # TXID
    # ========================================================

    if state.get("step") == "TXID":

        if not txt:

            update.message.reply_text(
                "❌ Please send the transaction ID."
            )

            return

        if txt in USED_TXIDS:

            update.message.reply_text(
                "❌ TXID already used."
            )

            return

        # ====================================================
        # SAVE TXID
        # ====================================================

        USED_TXIDS.add(
            txt
        )

        ref = (
            f"{uid}_"
            f"{txt[-6:]}"
        )

        context.bot_data[
            ref
        ] = state.copy()

        # ====================================================
        # ADMIN MESSAGE
        # ====================================================

        try:

            context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "💰 <b>Payment received</b>\n\n"
                    f"{state.get('name', 'Unknown')}"
                    f" "
                    f"({state.get('symbol', 'UNKNOWN')})\n"
                    f"Network: "
                    f"{state.get('network', 'N/A')}\n"
                    f"Package: "
                    f"{state.get('package', 'N/A')}\n"
                    f"Amount: "
                    f"{state.get('amount', 'N/A')} "
                    f"{state.get('network', '')}\n"
                    f"TXID: "
                    f"<code>{txt}</code>"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "START TRENDING",
                                callback_data=(
                                    f"ADMIN_START_{ref}"
                                ),
                            )
                        ]
                    ]
                ),
            )

        except Exception as e:

            print(
                f"Admin notification error: {e}"
            )

            update.message.reply_text(
                "❌ We received your TXID, "
                "but could not notify the admin. "
                "Please contact support."
            )

            return

        # ====================================================
        # USER CONFIRMATION
        # ====================================================

        update.message.reply_text(
            "✅ <b>Payment received.</b>\n\n"
            "Your payment is pending admin approval.",
            parse_mode="HTML",
        )

        USER_STATE.pop(
            uid,
            None,
        )

        return


# ============================================================
# ERROR HANDLER
# ============================================================

def error_handler(
    update,
    context,
):

    error = context.error

    print(
        f"Telegram bot error: {error}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    print(
        "========================================"
    )

    print(
        "🤖 Weibo Trending Bot is starting..."
    )

    print(
        f"Admin ID: {ADMIN_ID}"
    )

    print(
        "========================================"
    )

    updater = Updater(
        BOT_TOKEN,
        use_context=True,
    )

    dispatcher = updater.dispatcher

    # ========================================================
    # HANDLERS
    # ========================================================

    dispatcher.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    dispatcher.add_handler(
        CallbackQueryHandler(
            buttons,
        )
    )

    dispatcher.add_handler(
        MessageHandler(
            Filters.text & ~Filters.command,
            messages,
        )
    )

    dispatcher.add_error_handler(
        error_handler
    )

    # ========================================================
    # START POLLING
    # ========================================================

    print(
        "📡 Starting Telegram polling..."
    )

    updater.start_polling(
        drop_pending_updates=True
    )

    print(
        "✅ Bot is running."
    )

    updater.idle()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
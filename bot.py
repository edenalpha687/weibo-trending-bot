import os
import requests
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    raise RuntimeError("ADMIN_ID environment variable is missing.")

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    raise RuntimeError("ADMIN_ID must be a numeric Telegram user ID.")

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")


# ============================================================
# API
# ============================================================

DEX_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/"


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
# PRICE CONVERSION
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
        return None

    try:
        response = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price"
            f"?ids={coin_id}&vs_currencies=usd",
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        return data.get(coin_id, {}).get("usd")

    except Exception:
        return None


# ============================================================
# FETCH TOKEN DATA
# ============================================================

def fetch_dex_data(ca):
    try:
        response = requests.get(
            f"{DEX_TOKEN_URL}{ca}",
            timeout=15,
        )

        response.raise_for_status()

        pairs = response.json().get("pairs", [])

    except Exception:
        return None

    if not pairs:
        return None

    # Choose the pair with the highest liquidity.
    pair = max(
        pairs,
        key=lambda p: (
            (p.get("liquidity") or {}).get("usd") or 0
        ),
    )

    telegram = None
    twitter = None

    for link in (pair.get("info") or {}).get("links", []):
        if link.get("type") == "telegram":
            telegram = link.get("url")

        elif link.get("type") == "twitter":
            twitter = link.get("url")

    base_token = pair.get("baseToken") or {}
    info = pair.get("info") or {}
    liquidity = pair.get("liquidity") or {}

    return {
        "name": base_token.get("name") or "Unknown Token",
        "symbol": base_token.get("symbol") or "UNKNOWN",

        # Keep price as a string because DexScreener normally returns
        # priceUsd as a string.
        "price": pair.get("priceUsd") or "N/A",

        # Prevent NoneType formatting errors.
        "liquidity": liquidity.get("usd") or 0,
        "mcap": pair.get("fdv") or 0,

        "pair_url": pair.get("url") or "",
        "logo": info.get("imageUrl"),

        "telegram": telegram,
        "twitter": twitter,

        "chain": (pair.get("chainId") or "").lower(),
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
        "🐰 Boost Visibility for your Token in the Chinese market\n"
        "Fast Activation • Manual Control • Chinese visibility 🇨🇳",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ============================================================
# BUTTONS
# ============================================================

def buttons(update: Update, context: CallbackContext):
    query = update.callback_query

    query.answer()

    uid = query.from_user.id

    state = USER_STATE.get(uid)

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    if query.data == "START":

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

        context.bot.send_photo(
            uid,
            "https://raw.githubusercontent.com/edenalpha687/weibo-trending-bot/main/1190BF8B-063E-4AFE-8B1D-88E9BF653834.png",
            caption="Choose Network",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # --------------------------------------------------------
    # NETWORK
    # --------------------------------------------------------

    elif query.data.startswith("NET_"):

        network = query.data.replace("NET_", "")

        USER_STATE[uid] = {
            "step": "CA",
            "network": network,
        }

        try:
            query.message.delete()
        except Exception:
            pass

        context.bot.send_photo(
            uid,
            "https://raw.githubusercontent.com/edenalpha687/weibo-trending-bot/main/F33A4A2F-E8A9-440E-BA47-F7603692010A.png",
            caption="Enter Your Token CA",
        )

    # --------------------------------------------------------
    # PACKAGES
    # --------------------------------------------------------

    elif query.data == "PACKAGES":

        if not state:
            query.answer(
                "Session expired. Please start again.",
                show_alert=True,
            )
            return

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

        context.bot.send_message(
            uid,
            "🇨🇳 <b>Select Trending Duration</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # --------------------------------------------------------
    # PACKAGE SELECTED
    # --------------------------------------------------------

    elif query.data.startswith("PKG_"):

        if not state:
            query.answer(
                "Session expired. Please start again.",
                show_alert=True,
            )
            return

        pkg = query.data.replace("PKG_", "")

        if pkg not in PACKAGES:
            query.answer(
                "Invalid package.",
                show_alert=True,
            )
            return

        state["package"] = pkg

        usd_price = PACKAGES[pkg]

        coin_price = get_price(state["network"])

        # Prevent division by None/zero.
        if not coin_price or coin_price <= 0:
            query.answer(
                "Unable to get the current network price. Please try again.",
                show_alert=True,
            )
            return

        amount = round(
            (usd_price / coin_price) * 1.02,
            4,
        )

        state["amount"] = amount

        link = (
            state.get("telegram")
            or state.get("twitter")
            or state.get("pair_url")
            or ""
        )

        if link:
            name_line = (
                f'<a href="{link}">'
                f'<b>{state["name"]}</b>'
                f"</a>"
            )
        else:
            name_line = f'<b>{state["name"]}</b>'

        pair_url = state.get("pair_url") or ""

        if pair_url:
            price_line = (
                f'💰 <a href="{pair_url}">'
                f'Price: ${state.get("price", "N/A")}'
                f"</a>"
            )
        else:
            price_line = (
                f'💰 Price: ${state.get("price", "N/A")}'
            )

        liquidity = state.get("liquidity") or 0
        mcap = state.get("mcap") or 0

        caption = (
            "🚀 <b>Token Overview</b>\n\n"
            f"🐰 {name_line}\n"
            f"🔹 Symbol: {state['symbol']}\n"
            f"{price_line}\n"
            f"💧 Liquidity: ${liquidity:,.2f}\n"
            f"📊 Market Cap: ${mcap:,.0f}\n\n"
            f"⏱ Package: {pkg}\n"
            f"💎 Pay: {amount} {state['network']}"
        )

        try:
            query.message.delete()
        except Exception:
            pass

        logo = state.get("logo")

        if logo:
            context.bot.send_photo(
                uid,
                logo,
                caption=caption,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
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
                ),
            )
        else:
            context.bot.send_message(
                uid,
                caption,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
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
                ),
            )

    # --------------------------------------------------------
    # PAYMENT
    # --------------------------------------------------------

    elif query.data == "PAY":

        if not state:
            query.answer(
                "Session expired. Please start again.",
                show_alert=True,
            )
            return

        network = state.get("network")

        wallet = NETWORK_WALLETS.get(network)

        if not wallet:
            query.answer(
                f"{network} payment wallet is not configured.",
                show_alert=True,
            )
            return

        state["step"] = "TXID"

        context.bot.send_message(
            uid,
            f"🇨🇳 <b>Weibo Trending Activation | 激活确认</b>\n\n"
            f"┃ Network: <b>{network}</b>\n"
            f"┃ Package: <b>{state.get('package', 'N/A')}</b>\n\n"
            "──────────────\n"
            "✅ Activation Address\n"
            f"<code>{wallet}</code>\n"
            "──────────────\n"
            "🛎️ Send TXID to confirm",
            parse_mode="HTML",
        )

    # --------------------------------------------------------
    # ADMIN START TRENDING
    # --------------------------------------------------------

    elif query.data.startswith("ADMIN_START_") and uid == ADMIN_ID:

        ref = query.data.replace(
            "ADMIN_START_",
            "",
        )

        payload = context.bot_data.pop(
            ref,
            None,
        )

        if not payload:
            query.answer(
                "Payment session expired.",
                show_alert=True,
            )
            return

        if not CHANNEL_USERNAME:
            query.answer(
                "CHANNEL_USERNAME is not configured.",
                show_alert=True,
            )
            return

        context.bot.send_message(
            CHANNEL_USERNAME,
            f"🔥 Weibo Trending Live 🇨🇳\n\n"
            f"{payload.get('name', 'Unknown')} "
            f"({payload.get('symbol', 'UNKNOWN')})\n"
            f"CA: {payload.get('ca', 'N/A')}\n"
            f"Started: "
            f"{datetime.utcnow().strftime('%H:%M UTC')}",
        )

        query.edit_message_text(
            "Trending activated."
        )


# ============================================================
# TEXT HANDLER
# ============================================================

def messages(update: Update, context: CallbackContext):

    uid = update.message.from_user.id

    txt = update.message.text.strip()

    state = USER_STATE.get(uid)

    if not state:
        return

    # ========================================================
    # TOKEN CONTRACT ADDRESS
    # ========================================================

    if state["step"] == "CA":

        data = fetch_dex_data(txt)

        if not data:
            update.message.reply_text(
                "❌ Token not found or DexScreener is unavailable. "
                "Please check the contract address and try again."
            )
            return

        chain_map = {
            "SOL": ["solana"],
            "ETH": ["ethereum", "eth"],
            "BSC": ["bsc"],
            "BASE": ["base"],
            "SUI": ["sui"],
            "XRP": ["xrpl", "xrp"],
        }

        token_chain = (
            data.get("chain") or ""
        ).lower()

        selected_network = state.get(
            "network",
            "",
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
                f"❌ Wrong network.\n"
                f"You selected {selected_network} "
                f"but token appears on "
                f"{token_chain.upper()}."
            )
            return

        state.update(data)

        state["ca"] = txt

        link = (
            data.get("telegram")
            or data.get("twitter")
            or data.get("pair_url")
            or ""
        )

        if link:
            name_line = (
                f'<a href="{link}">'
                f'<b>{data["name"]}</b>'
                f"</a>"
            )
        else:
            name_line = f'<b>{data["name"]}</b>'

        pair_url = data.get("pair_url") or ""

        if pair_url:
            price_line = (
                f'💰 <a href="{pair_url}">'
                f'Price: ${data.get("price", "N/A")}'
                f"</a>"
            )
        else:
            price_line = (
                f'💰 Price: ${data.get("price", "N/A")}'
            )

        # These values are guaranteed to be numeric now.
        liquidity = data.get("liquidity") or 0
        mcap = data.get("mcap") or 0

        caption = (
            "🚀 <b>Token Overview</b>\n\n"
            f"🐰 {name_line}\n"
            f"🔹 Symbol: {data['symbol']}\n"
            f"{price_line}\n"
            f"💧 Liquidity: ${liquidity:,.2f}\n"
            f"📊 Market Cap: ${mcap:,.0f}"
        )

        logo = data.get("logo")

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

        if logo:
            context.bot.send_photo(
                uid,
                logo,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        else:
            context.bot.send_message(
                uid,
                caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

    # ========================================================
    # TXID
    # ========================================================

    elif state["step"] == "TXID":

        if txt in USED_TXIDS:
            update.message.reply_text(
                "❌ TXID already used."
            )
            return

        USED_TXIDS.add(txt)

        ref = f"{uid}_{txt[-6:]}"

        context.bot_data[ref] = state.copy()

        context.bot.send_message(
            ADMIN_ID,
            f"💰 <b>Payment received</b>\n\n"
            f"{state.get('name', 'Unknown')} "
            f"({state.get('symbol', 'UNKNOWN')})\n"
            f"Network: {state.get('network', 'N/A')}\n"
            f"Package: {state.get('package', 'N/A')}\n"
            f"TXID: <code>{txt}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "START TRENDING",
                            callback_data=f"ADMIN_START_{ref}",
                        )
                    ]
                ]
            ),
        )

        update.message.reply_text(
            "✅ Payment received.\n\n"
            "Your payment is pending admin approval."
        )

        USER_STATE.pop(uid, None)


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    updater = Updater(
        BOT_TOKEN,
        use_context=True,
    )

    dispatcher = updater.dispatcher

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

    print("🤖 Weibo Trending Bot is starting...")

    updater.start_polling()

    updater.idle()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
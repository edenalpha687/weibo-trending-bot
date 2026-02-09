import os
import requests
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

DEX_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/"

NETWORK_WALLETS = {
    "SOL": os.getenv("SOL_WALLET"),
    "ETH": os.getenv("ETH_WALLET"),
    "BSC": os.getenv("BSC_WALLET"),
    "BASE": os.getenv("BASE_WALLET"),
    "SUI": os.getenv("SUI_WALLET"),
    "XRP": os.getenv("XRP_WALLET"),
}

PACKAGES = {
    "24H": 2500,
    "48H": 5500,
    "72H": 8000,
    "96H": 10500,
    "120H": 13000,
    "144H": 15500,
    "168H": 18000,
}

USER_STATE = {}
USED_TXIDS = set()


# ===== PRICE CONVERSION =====
def get_price(symbol):
    ids = {
        "SOL": "solana",
        "ETH": "ethereum",
        "BSC": "binancecoin",
        "BASE": "ethereum",
        "SUI": "sui",
        "XRP": "ripple",
    }

    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={ids[symbol]}&vs_currencies=usd",
            timeout=10,
        ).json()

        return list(r.values())[0]["usd"]
    except:
        return None


# ===== FETCH TOKEN DATA =====
def fetch_dex_data(ca):
    r = requests.get(f"{DEX_TOKEN_URL}{ca}", timeout=15)
    pairs = r.json().get("pairs", [])
    if not pairs:
        return None

    pair = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd", 0))

    telegram = None
    twitter = None

    for l in (pair.get("info") or {}).get("links", []):
        if l.get("type") == "telegram":
            telegram = l.get("url")
        if l.get("type") == "twitter":
            twitter = l.get("url")

    return {
        "name": pair["baseToken"]["name"],
        "symbol": pair["baseToken"]["symbol"],
        "price": pair.get("priceUsd"),
        "liquidity": (pair.get("liquidity") or {}).get("usd"),
        "mcap": pair.get("fdv"),
        "pair_url": pair.get("url"),
        "logo": (pair.get("info") or {}).get("imageUrl"),
        "telegram": telegram,
        "twitter": twitter,
    }


# ===== START =====
def start(update: Update, context: CallbackContext):
    kb = [[InlineKeyboardButton("🐰Activate Weibo Trending 🇨🇳", callback_data="START")]]

    update.message.reply_text(
        "🔥 WEIBO TRENDING 🇨🇳 🐇\n\n"
        "🐰Boost Visibility for your Token in the Chinese market\n"
        "Fast Activation • Manual Control • Chinese visibility 🇨🇳",
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ===== BUTTONS =====
def buttons(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    uid = q.from_user.id
    state = USER_STATE.get(uid)

    if q.data == "START":
        kb = [
            [InlineKeyboardButton("SOL", callback_data="NET_SOL"),
             InlineKeyboardButton("ETH", callback_data="NET_ETH"),
             InlineKeyboardButton("BSC", callback_data="NET_BSC")],
            [InlineKeyboardButton("SUI", callback_data="NET_SUI"),
             InlineKeyboardButton("BASE", callback_data="NET_BASE"),
             InlineKeyboardButton("XRP", callback_data="NET_XRP")]
        ]

        q.message.delete()

        context.bot.send_photo(
            uid,
            "https://raw.githubusercontent.com/edenalpha687/weibo-trending-bot/main/1190BF8B-063E-4AFE-8B1D-88E9BF653834.png",
            caption="Choose Network",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    elif q.data.startswith("NET_"):
        network = q.data.replace("NET_", "")
        USER_STATE[uid] = {"step": "CA", "network": network}

        q.message.delete()

        context.bot.send_photo(
            uid,
            "https://raw.githubusercontent.com/edenalpha687/weibo-trending-bot/main/F33A4A2F-E8A9-440E-BA47-F7603692010A.png",
            caption="Enter Your Token CA",
        )

    elif q.data == "PACKAGES":
        kb = [
            [InlineKeyboardButton("24H • $2,500", callback_data="PKG_24H"),
             InlineKeyboardButton("48H • $5,500", callback_data="PKG_48H")],

            [InlineKeyboardButton("72H • $8,000", callback_data="PKG_72H"),
             InlineKeyboardButton("96H • $10,500", callback_data="PKG_96H")],

            [InlineKeyboardButton("120H • $13,000", callback_data="PKG_120H"),
             InlineKeyboardButton("144H • $15,500", callback_data="PKG_144H")],

            [InlineKeyboardButton("168H • $18,000", callback_data="PKG_168H")],

            [InlineKeyboardButton("⬅️ Back", callback_data="START")]
        ]

        context.bot.send_message(
            uid,
            "🇨🇳 <b>Select Trending Duration</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    elif q.data.startswith("PKG_"):
        pkg = q.data.replace("PKG_", "")
        state["package"] = pkg

        usd_price = PACKAGES[pkg]
        coin_price = get_price(state["network"])
        amount = round((usd_price / coin_price) * 1.02, 4)

        state["amount"] = amount

        link = state.get("telegram") or state.get("twitter") or state["pair_url"]
        name_line = f'<a href="{link}"><b>{state["name"]}</b></a>'

        caption = (
            "✨ <b>Token Overview | 项目信息</b>\n\n"
            f"{name_line}\n"
            f"┃ Symbol: <b>{state['symbol']}</b>\n"
            f'┃ <a href="{state["pair_url"]}">Price: ${state["price"]}</a>\n'
            f"┃ Liquidity: ${state['liquidity']:,.2f}\n"
            f"┃ Market Cap: ${state['mcap']:,.0f}\n\n"
            "──────────────\n"
            f"⏱ Package: <b>{pkg}</b>\n"
            f"💎 Pay: <b>{amount} {state['network']}</b>\n"
            "──────────────"
        )

        q.message.delete()

        context.bot.send_photo(
            uid,
            state["logo"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data="PAY")],
                [InlineKeyboardButton("⬅️ Back", callback_data="PACKAGES")],
            ]),
        )

    elif q.data == "PAY":
        wallet = NETWORK_WALLETS[state["network"]]
        state["step"] = "TXID"

        context.bot.send_message(
            uid,
            f"🇨🇳 <b>Weibo Trending Activation | 激活确认</b>\n\n"
            f"┃ Network: <b>{state['network']}</b>\n"
            f"┃ Package: <b>{state['package']}</b>\n\n"
            "──────────────\n"
            "<b>Activation Address</b>\n"
            f"<code>{wallet}</code>\n"
            "──────────────\n"
            "🛎️ Send TXID to confirm",
            parse_mode="HTML",
        )

    elif q.data.startswith("ADMIN_START_") and uid == ADMIN_ID:
        ref = q.data.replace("ADMIN_START_", "")
        payload = context.bot_data.pop(ref, None)

        context.bot.send_message(
            CHANNEL_USERNAME,
            f"🔥 Weibo Trending Live 🇨🇳\n\n"
            f"{payload['name']} ({payload['symbol']})\n"
            f"CA: {payload['ca']}\n"
            f"Started: {datetime.utcnow().strftime('%H:%M UTC')}",
        )

        q.edit_message_text("Trending activated.")


# ===== TEXT HANDLER =====
def messages(update: Update, context: CallbackContext):
    uid = update.message.from_user.id
    txt = update.message.text.strip()
    state = USER_STATE.get(uid)

    if not state:
        return

    if state["step"] == "CA":
        data = fetch_dex_data(txt)

        if not data:
            update.message.reply_text("Token not found.")
            return

        state.update(data)
        state["ca"] = txt

        link = data.get("telegram") or data.get("twitter") or data["pair_url"]
        name_line = f'<a href="{link}"><b>{data["name"]}</b></a>'

        caption = (
            "✨ <b>Token Overview</b>\n\n"
            f"{name_line}\n"
            f"Symbol: {data['symbol']}\n"
            f'<a href="{data["pair_url"]}">Price: ${data["price"]}</a>\n'
            f"Liquidity: ${data['liquidity']:,.2f}\n"
            f"Market Cap: ${data['mcap']:,.0f}"
        )

        context.bot.send_photo(
            uid,
            data["logo"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Continue", callback_data="PACKAGES")]
            ]),
        )

    elif state["step"] == "TXID":
        if txt in USED_TXIDS:
            update.message.reply_text("TXID already used.")
            return

        USED_TXIDS.add(txt)

        ref = f"{uid}_{txt[-6:]}"
        context.bot_data[ref] = state.copy()

        context.bot.send_message(
            ADMIN_ID,
            f"Payment received\n\n"
            f"{state['name']} ({state['symbol']})\n"
            f"Network: {state['network']}\n"
            f"Package: {state['package']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("START TRENDING", callback_data=f"ADMIN_START_{ref}")]
            ]),
        )

        update.message.reply_text("Payment pending admin approval.")
        USER_STATE.pop(uid, None)


def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(buttons))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, messages))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()

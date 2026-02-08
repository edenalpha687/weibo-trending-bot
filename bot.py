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

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

WEBHOOK_BASE = "https://worker-production-56e9.up.railway.app"

ENTER_CA_IMAGE_URL = "https://raw.githubusercontent.com/edenalpha687/pumpfun-trending-bot/main/589CF67D-AF43-433F-A8AB-B43E9653E703.png"

DEX_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/"

# ================= MULTICHAIN CONFIG =================
NETWORK_WALLETS = {
    "SOL": os.getenv("SOL_WALLET"),
    "ETH": os.getenv("ETH_WALLET"),
    "BSC": os.getenv("BSC_WALLET"),
    "BASE": os.getenv("BASE_WALLET"),
    "SUI": os.getenv("SUI_WALLET"),
    "XRP": os.getenv("XRP_WALLET"),
}

# USD pricing
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

# ================= HELPERS =================
def fmt_usd(v):
    if not v:
        return "—"
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v/1_000:.2f}K"
    return f"${v:.2f}"


def fetch_dex_data(ca):
    r = requests.get(f"{DEX_TOKEN_URL}{ca}", timeout=15)
    r.raise_for_status()
    pairs = r.json().get("pairs", [])
    if not pairs:
        return None

    pair = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd", 0))

    telegram_link = None
    for l in (pair.get("info") or {}).get("links", []):
        if l.get("type") == "telegram":
            telegram_link = l.get("url")

    return {
        "name": pair["baseToken"]["name"],
        "symbol": pair["baseToken"]["symbol"],
        "price": pair.get("priceUsd"),
        "liquidity": (pair.get("liquidity") or {}).get("usd"),
        "mcap": pair.get("fdv"),
        "pair_url": pair.get("url"),
        "logo": (pair.get("info") or {}).get("imageUrl"),
        "telegram": telegram_link,
    }


# price conversion
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


def activate_trending(payload):
    requests.post(
        f"{WEBHOOK_BASE}/activate",
        json={
            "mint": payload["ca"],
            "name": payload["name"],
            "price": payload["price"],
            "mcap": payload["mcap"],
            "logo": payload["logo"],
            "dex": payload["pair_url"],
            "network": payload["network"],
        },
        timeout=10,
    )


# ================= START =================
def start(update: Update, context: CallbackContext):
    kb = [
        [
            InlineKeyboardButton("SOL", callback_data="NET_SOL"),
            InlineKeyboardButton("ETH", callback_data="NET_ETH"),
            InlineKeyboardButton("BSC", callback_data="NET_BSC"),
        ],
        [
            InlineKeyboardButton("SUI", callback_data="NET_SUI"),
            InlineKeyboardButton("BASE", callback_data="NET_BASE"),
            InlineKeyboardButton("XRP", callback_data="NET_XRP"),
        ],
    ]

    update.message.reply_text(
        "🔥 Weibo Trending\n\n"
        "Boost visibility for your token.\n"
        "Fast activation • Manual control • Real visibility",
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ================= BUTTONS =================
def buttons(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    uid = q.from_user.id
    state = USER_STATE.get(uid)

    if q.data.startswith("NET_"):
        network = q.data.replace("NET_", "")
        USER_STATE[uid] = {"step": "CA", "network": network}

        q.message.delete()
        sent = context.bot.send_photo(
            chat_id=uid,
            photo=ENTER_CA_IMAGE_URL,
            caption="🟢 Please enter your token contract address (CA)",
        )
        USER_STATE[uid]["prompt_msg_id"] = sent.message_id

    elif q.data == "PACKAGES":
        kb = [[InlineKeyboardButton(k, callback_data=f"PKG_{k}")]
              for k in PACKAGES.keys()]

        context.bot.send_message(
            chat_id=uid,
            text="Select trending duration:",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    elif q.data.startswith("PKG_"):
        pkg = q.data.replace("PKG_", "")
        state["package"] = pkg

        usd_price = PACKAGES[pkg]
        coin_price = get_price(state["network"])

        if not coin_price:
            context.bot.send_message(chat_id=uid, text="Price fetch error.")
            return

        amount = round((usd_price / coin_price) * 1.02, 4)
        state["amount"] = amount

        caption = (
            "🟢 Token Detected\n\n"
            f"Name: {state['name']}\n"
            f"💠 Symbol: {state['symbol']}\n"
            f"💵 Price: ${state['price']}\n"
            f"💧 Liquidity: {fmt_usd(state['liquidity'])}\n"
            f"📊 Market Cap: {fmt_usd(state['mcap'])}\n\n"
            f"⏱ Selected Package: {pkg}\n"
            f"💰 Pay: {amount} {state['network']}"
        )

        q.message.delete()
        context.bot.send_photo(
            chat_id=uid,
            photo=state["logo"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data="PAY")],
                [InlineKeyboardButton("⬅️ Back", callback_data="PACKAGES")],
            ]),
        )

    elif q.data == "PAY":
        wallet = NETWORK_WALLETS[state["network"]]
        state["step"] = "TXID"

        context.bot.send_message(
            chat_id=uid,
            text=(
                f"Activation address ({state['network']})\n\n"
                f"`{wallet}`\n\n"
                "🛎️ Send TXID to confirm"
            ),
            parse_mode="Markdown",
        )

    elif q.data.startswith("ADMIN_START_") and uid == ADMIN_ID:
        ref = q.data.replace("ADMIN_START_", "")
        payload = context.bot_data.pop(ref, None)
        if not payload:
            return

        activate_trending(payload)

        context.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=(
                "🔥 Weibo Trending Live\n\n"
                f"{payload['name']} ({payload['symbol']})\n"
                f"CA: {payload['ca']}\n"
                f"Network: {payload['network']}\n"
                f"Started: {datetime.utcnow().strftime('%H:%M UTC')}"
            ),
        )

        q.edit_message_text("✅ Trending activated.")


# ================= TEXT =================
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
        state["step"] = "PREVIEW"

        caption = (
            "🟢 Token Detected\n\n"
            f"Name: {data['name']}\n"
            f"💠 Symbol: {data['symbol']}\n"
            f"💵 Price: ${data['price']}\n"
            f"💧 Liquidity: {fmt_usd(data['liquidity'])}\n"
            f"📊 Market Cap: {fmt_usd(data['mcap'])}"
        )

        context.bot.send_photo(
            chat_id=uid,
            photo=data["logo"],
            caption=caption,
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
            chat_id=ADMIN_ID,
            text=(
                "🛎️ Payment received\n\n"
                f"{state['name']} ({state['symbol']})\n"
                f"Network: {state['network']}\n"
                f"Package: {state['package']}"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ START TRENDING", callback_data=f"ADMIN_START_{ref}")]
            ]),
        )

        update.message.reply_text(
            "🟢 Payment confirmed\n\n"
            f"Token: {state['name']} ({state['symbol']})\n"
            f"Package: {state['package']}\n"
            f"Amount: {state['amount']} {state['network']}\n"
            "Status: Pending activation"
        )

        USER_STATE.pop(uid, None)


# ================= MAIN =================
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

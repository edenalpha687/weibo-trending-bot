import os
import re
import requests
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

WEBHOOK_BASE = "https://worker-production-56e9.up.railway.app"

DEX_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/"
HELIUS_RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

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

# ================= HELPERS =================
def fmt_usd(v):
    if not v:
        return "—"
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v/1_000:.2f}K"
    return f"${v:.2f}"


def get_crypto_price(symbol):
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


def fetch_dex_data(ca):
    r = requests.get(f"{DEX_TOKEN_URL}{ca}", timeout=15)
    r.raise_for_status()
    pairs = r.json().get("pairs", [])
    if not pairs:
        return None

    pair = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd", 0))

    telegram_link = None
    twitter_link = None
    for l in (pair.get("info") or {}).get("links", []):
        if l.get("type") == "telegram":
            telegram_link = l.get("url")
        if l.get("type") == "twitter":
            twitter_link = l.get("url")

    return {
        "name": pair["baseToken"]["name"],
        "symbol": pair["baseToken"]["symbol"],
        "price": pair.get("priceUsd"),
        "liquidity": (pair.get("liquidity") or {}).get("usd"),
        "mcap": pair.get("fdv"),
        "pair_url": pair.get("url"),
        "logo": (pair.get("info") or {}).get("imageUrl"),
        "telegram": telegram_link,
        "twitter": twitter_link,
    }


def verify_txid(txid):
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignatureStatuses",
            "params": [[txid], {"searchTransactionHistory": True}],
        }
        r = requests.post(HELIUS_RPC_URL, json=payload, timeout=15)
        status = r.json()["result"]["value"][0]

        if status and status.get("confirmationStatus") in ("confirmed", "finalized"):
            return "OK"
        return "PENDING"
    except:
        return "PENDING"


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
        },
        timeout=10,
    )


# ================= START =================
def start(update: Update, context: CallbackContext):
    kb = [[InlineKeyboardButton("🐰Activate Weibo Trending 🇨🇳", callback_data="START")]]

    update.message.reply_text(
        "🔥 WEIBO TRENDING 🇨🇳 🐇\n\n"
        "🐰Boost Visibility for your Token in the Chinese market\n"
        "Fast Activation • Manual Control • Chinese visibility 🇨🇳",
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ================= BUTTONS =================
def buttons(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    uid = q.from_user.id

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
            "🇨🇳 Select Trending Duration",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    elif q.data.startswith("PKG_"):
        pkg = q.data.replace("PKG_", "")
        state = USER_STATE[uid]

        usd_price = PACKAGES[pkg]
        coin_price = get_crypto_price(state["network"])
        amount = round((usd_price / coin_price) * 1.02, 4)

        state["package"] = pkg
        state["amount"] = amount

        name_link = state.get("telegram") or state.get("twitter")
        name_line = f'<a href="{name_link}">{state["name"]}</a>' if name_link else state["name"]

        caption = (
            "✨ <b>Token Overview | 项目信息</b>\n\n"
            f"{name_line}\n"
            f"┃ Symbol: <b>{state['symbol']}</b>\n"
            f'┃ <a href="{state["pair_url"]}">Price: ${state["price"]}</a>\n'
            f"┃ Liquidity: {fmt_usd(state['liquidity'])}\n"
            f"┃ Market Cap: {fmt_usd(state['mcap'])}\n\n"
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
        state = USER_STATE[uid]
        wallet = NETWORK_WALLETS[state["network"]]
        state["step"] = "TXID"

        context.bot.send_message(
            uid,
            f"🇨🇳 <b>Weibo Trending Activation | 激活确认</b>\n\n"
            f"┃ Network: <b>{state['network']}</b>\n"
            f"┃ Package: <b>{state['package']}</b>\n\n"
            "──────────────\n"
            "✅ <b>Activation Address</b>\n"
            f"<code>{wallet}</code>\n"
            "──────────────\n"
            "🛎️ Send TXID to confirm",
            parse_mode="HTML",
        )


# ================= TEXT HANDLER =================
def messages(update: Update, context: CallbackContext):
    uid = update.message.from_user.id
    txt = update.message.text.strip()
    state = USER_STATE.get(uid)

    if not state:
        return

    if state.get("step") == "CA":
        data = fetch_dex_data(txt)
        if not data:
            update.message.reply_text("Token not found.")
            return

        state.update(data)
        state["ca"] = txt

        context.bot.send_message(
            uid,
            "Token detected successfully 🇨🇳",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Continue", callback_data="PACKAGES")]]
            ),
        )


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

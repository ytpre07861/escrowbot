import re
import sqlite3
import random
import string
import telebot

# --- CONFIGURATION ---
TOKEN = "8884697639:AAGmLQ6fpnSOnLQqh_FCpTloSthDlkO3y8E"
bot = telebot.TeleBot(TOKEN)

DB_NAME = "escrow_market.db"

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            trade_id TEXT PRIMARY KEY,
            buyer_user TEXT,
            seller_user TEXT,
            received_amount REAL,
            release_amount REAL,
            escrowed_by TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- ADMIN CHECK FUNCTION ---
def is_admin(message):
    # Private chat me check karne ki zaroori nahi, par group me strict check hoga
    if message.chat.type in ['group', 'supergroup']:
        try:
            member = bot.get_chat_member(message.chat.id, message.from_user.id)
            # Khali 'administrator' aur 'creator' (owner) ko allow karega
            if member.status in ['administrator', 'creator']:
                return True
            else:
                return False
        except Exception:
            return False
    return True # Private chat me allowed

# --- FEES CALCULATION ---
def calculate_release(received_amount):
    if received_amount <= 500:
        fee = 5.0
    elif received_amount <= 1000:
        fee = 10.0
    elif received_amount <= 2000:
        fee = 20.0
    elif received_amount <= 3000:
        fee = round(received_amount * 0.025, 2)
    else:
        fee = round(received_amount * 0.02, 2)
        
    possible_deal = received_amount - fee
    return max(0.0, possible_deal)

def generate_trade_id():
    return "TID" + "".join(random.choices(string.ascii_uppercase, k=6))

# --- ROBUST TEXT PARSER ---
def parse_form_text(text):
    buyer, seller = "Not Filled", "Not Filled"
    if not text:
        return buyer, seller
        
    lines = text.split('\n')
    for line in lines:
        cleaned_line = line.replace(" ", "").upper()
        
        # Checking for Seller
        if "SELLER" in cleaned_line or "ꜱᴇʟʟᴇʀ" in line:
            if "@" in line:
                parts = line.split("@")
                if len(parts) > 1:
                    seller = "@" + parts[-1].strip().split()[0]
                    
        # Checking for Buyer
        if "BUYER" in cleaned_line or "ʙᴜʏᴇʀ" in line:
            if "@" in line:
                parts = line.split("@")
                if len(parts) > 1:
                    buyer = "@" + parts[-1].strip().split()[0]
                    
    return buyer, seller

# --- COMMAND: /ADD [AMOUNT] ---
@bot.message_handler(commands=['add'])
def add_deal(message):
    # Strict Admin Filter
    if not is_admin(message):
        return  # Normal member chalayega toh bot kuch respond nahi karega

    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ Please reply directly to the Deal Form message.")
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Format: /add [amount]")
        return

    try:
        received_amt = float(args[1])
    except ValueError:
        bot.reply_to(message, "❌ Invalid Amount format.")
        return

    target_msg = message.reply_to_message
    form_text = target_msg.text or target_msg.caption or ""
    buyer, seller = parse_form_text(form_text)

    release_amt = calculate_release(received_amt)
    trade_id = generate_trade_id()
    escrower = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name

    # DB Save
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO deals (trade_id, buyer_user, seller_user, received_amount, release_amount, escrowed_by, status)
        VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
    ''', (trade_id, buyer, seller, received_amt, release_amt, escrower))
    conn.commit()
    conn.close()

    # Exact Layout
    response_text = (
        f"📥 Received Amount: ₹{received_amt:.2f}\n"
        f"📤 Release/Refund Amount: ₹{release_amt:.2f}\n"
        f"🆔 Trade ID: #{trade_id}\n\n"
        f"Continue the Deal\n"
        f"Buyer: {buyer}\n"
        f"Seller: {seller}\n\n"
        f"🛡️ Escrowed By: {escrower}"
    )
    bot.reply_to(message, response_text)

# --- COMMAND: /RELEASE [TRADE_ID] ---
@bot.message_handler(commands=['release'])
def release_deal(message):
    # Strict Admin Filter
    if not is_admin(message):
        return  # Normal member par silent rahega

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Format: /release [Trade ID]")
        return

    trade_id = args[1].replace("#", "").upper().strip()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT buyer_user, seller_user, received_amount, release_amount, escrowed_by, status FROM deals WHERE trade_id = ?", (trade_id,))
    row = cursor.fetchone()

    if not row:
        bot.reply_to(message, "❌ Database me yeh Trade ID nahi mili!")
        conn.close()
        return

    buyer, seller, received_amt, release_amt, escrower, status = row

    if status == 'COMPLETED':
        bot.reply_to(message, "⚠️ Yeh deal pehle hi complete ho chuki hai.")
        conn.close()
        return

    cursor.execute("UPDATE deals SET status = 'COMPLETED' WHERE trade_id = ?", (trade_id,))
    conn.commit()
    conn.close()

    # Exact Release Layout
    completion_text = (
        f"✅ Deal Completed\n"
        f"🆔 Trade ID: #{trade_id}\n"
        f"ℹ️ Received: ₹{received_amt:.2f}\n"
        f"ℹ️ Total Released: ₹{release_amt:.2f}\n\n"
        f"Buyer: {buyer}\n"
        f"Seller: {seller}\n\n"
        f"🛡️ Escrowed By: {escrower}"
    )
    bot.reply_to(message, completion_text)

if __name__ == "__main__":
    print("🚀 Secured Admin-Only Bot is Online...")
    bot.infinity_polling()

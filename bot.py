import requests
import asyncio
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# ----------- 1. KEEP ALIVE SERVER (For Render) -----------
app = Flask('')

@app.route('/')
def home():
    return "TTC Bot is Running 24/7!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run)
    t.start()

# ----------- 2. CONFIGURATION -----------
BOT_TOKEN = "8754175364:AAFzARc4x8QXNl-1ziEr6K-YNnYV2YP6K0k" # আপনার টোকেন এখানে বসান

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# ----------- 3. DATA SCRAPER -----------
def get_data(tid):
    url = f"https://billpay.sonalibank.com.bd/TTCFee/Home/Voucher/{tid}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        data = {
            "Transaction ID": tid, "College": "", "Name": "", "Roll/Reg": "",
            "Mobile": "", "St. Year": "", "Session": "",
            "Amount(BDT)": "", "Date": "Not Found"
        }
        
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                key = cols[0].text.strip().replace(":", "")
                val = cols[1].text.strip()
                
                if "College" in key: data["College"] = val
                elif "Roll/Reg" in key: data["Roll/Reg"] = val
                elif "Name" in key: data["Name"] = val
                elif "Mobile" in key: data["Mobile"] = val
                elif "St. Year" in key: data["St. Year"] = val
                elif "Session" in key: data["Session"] = val
                elif "Amount" in key: data["Amount(BDT)"] = val
                elif "Date" in key: data["Date"] = val

        if data["Date"] == "Not Found":
            date_tag = soup.find(string=lambda x: x and "Date" in x)
            if date_tag:
                data["Date"] = date_tag.parent.get_text().replace("Date", "").replace(":", "").strip()

        return data
    except:
        return None

# ----------- 4. SEND RESULT -----------
async def process_roll(update_or_query, data_list):
    final_text = ""
    unique_phones = []
    
    for i, data in enumerate(data_list, 1):
        phone = data["Mobile"]
        wa_phone = "880" + phone[1:] if phone.startswith("0") else phone
        
        final_text += f"📄 Result {i}\n<pre>\nTransaction ID: {data['Transaction ID']}\nCollege       : {data['College']}\nRoll/Reg      : {data['Roll/Reg']}\nName          : {data['Name']}\nMobile        : {data['Mobile']}\nSt. Year      : {data['St. Year']}\nSession       : {data['Session']}\nAmount(BDT)   : {data['Amount(BDT)']}\nDate          : {data['Date']}\n</pre>\n\n"
        
        if wa_phone not in unique_phones:
            unique_phones.append(wa_phone)

    keyboard = []
    for ph in unique_phones:
        keyboard.append([
            InlineKeyboardButton("📱 WhatsApp", url=f"https://wa.me/{ph}"),
            InlineKeyboardButton("📢 Telegram", url=f"https://t.me/{ph}")
        ])
    
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    await msg_source.reply_text(final_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ----------- 5. CORE SEARCH ENGINE -----------
async def run_search(update_or_query, context, start_r, end_r):
    rolls = list(range(start_r, end_r + 1))
    context.user_data["current_end"] = end_r
    
    msg_source = update_or_query.message if hasattr(update_or_query, 'message') else update_or_query
    status_msg = await msg_source.reply_text("⏳ Processing...")
    
    total_found = 0
    for i, roll in enumerate(rolls, 1):
        try:
            url = f"https://billpay.sonalibank.com.bd/TTCFee/Home/Search?searchStr={roll}"
            r = requests.get(url, headers=headers, timeout=10)
            
            if "Details" in r.text:
                soup = BeautifulSoup(r.text, "html.parser")
                links = soup.select("a[href*='Voucher']")
                data_list = []
                for link in links:
                    tid = link['href'].split("/")[-1]
                    d = get_data(tid)
                    if d and d["Name"]: data_list.append(d)
                
                if data_list:
                    total_found += 1
                    await process_roll(update_or_query, data_list)

            # আপনি যেভাবে চেয়েছেন সেই স্ট্যাটাস আপডেট
            await status_msg.edit_text(
                f"⏳ Processing...\n"
                f"🔢 Roll: {roll}\n"
                f"📊 Found: {total_found}\n"
                f"✅ Progress: {i}/{len(rolls)}"
            )
        except: continue

    # রেজাল্ট শেষে আপনার দেওয়া ফরম্যাট এবং নেক্সট বাটন
    next_kb = [[InlineKeyboardButton("👉 Next 500?", callback_data="next_500")]]
    await msg_source.reply_text(
        f"✅ Done!\n📊 Total: {total_found}",
        reply_markup=InlineKeyboardMarkup(next_kb)
    )

# ----------- 6. HANDLERS -----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Start", callback_data="btn_ready")]]
    await update.message.reply_text("বটটি শুরু করতে নিচের বাটনে ক্লিক করুন:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        if "-" in text:
            s, e = map(int, text.split("-"))
            await run_search(update, context, s, e)
        else:
            r = int(text)
            await run_search(update, context, r, r)
    except:
        pass

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "btn_ready":
        await query.message.reply_text("🚀 Ready!")
    
    elif query.data == "next_500":
        last_end = context.user_data.get("current_end", 0)
        if last_end > 0:
            await run_search(query, context, last_end + 1, last_end + 500)

# ----------- 7. MAIN START -----------
if __name__ == "__main__":
    keep_alive()
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.run_polling()

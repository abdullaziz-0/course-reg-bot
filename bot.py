import os
import json
import logging
from datetime import date

import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ---------- الإعدادات (تُقرأ من متغيرات البيئة على Railway) ----------
BOT_TOKEN = os.environ["BOT_TOKEN"]
SHEET_NAME = os.environ.get("SHEET_NAME", "طلاب 481")
GOOGLE_CREDS_JSON = os.environ["GOOGLE_CREDS_JSON"]  # محتوى ملف الـ JSON كامل كنص

# ---------- الاتصال بـ Google Sheets ----------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(GOOGLE_CREDS_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
spreadsheet = gc.open(SHEET_NAME)

# رؤوس الأعمدة بالترتيب المتوقع في كل شيت مادة
HEADERS = ["الاسم", "رقم الجوال", "يوزر تلقرام", "السعر الكلي", "المدفوع", "الباقي", "تاريخ آخر دفعة", "ملاحظات"]

# الكلمات المفتاحية اللي نبحث عنها بالرسالة -> تطابقها لعمود
FIELD_MAP = {
    "الاسم": "name",
    "الجوال": "phone",
    "رقم الجوال": "phone",
    "تلقرام": "telegram",
    "يوزر": "telegram",
    "المادة": "subject",
    "السعر": "price",
    "المدفوع": "paid",
}


def parse_message(text: str) -> dict:
    """يفصل الرسالة سطر سطر بصيغة 'الحقل: القيمة' ويرجع dict."""
    data = {}
    for line in text.strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        field = FIELD_MAP.get(key)
        if field:
            data[field] = value
    return data


def find_or_create_worksheet(subject: str):
    """يرجع الشيت المطابق لاسم المادة، أو يرفع خطأ إذا ما لقاه."""
    try:
        return spreadsheet.worksheet(subject)
    except gspread.WorksheetNotFound:
        return None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    data = parse_message(text)

    required = ["name", "phone", "telegram", "subject", "price", "paid"]
    missing = [f for f in required if f not in data]
    if missing:
        await update.message.reply_text(
            "الرسالة ناقصة أو صيغتها غير صحيحة. تأكد من إرسال كل السطور التالية:\n\n"
            "الاسم: ...\n"
            "الجوال: ...\n"
            "تلقرام: ...\n"
            "المادة: ...\n"
            "السعر: ...\n"
            "المدفوع: ..."
        )
        return

    ws = find_or_create_worksheet(data["subject"])
    if ws is None:
        await update.message.reply_text(
            f"ما لقيت شيت باسم المادة '{data['subject']}'. تأكد من كتابة اسم المادة بالضبط "
            "زي ما هو مكتوب في الشيت (تأكد من التطابق الكامل بالحروف)."
        )
        return

    try:
        price = float(data["price"])
        paid = float(data["paid"])
    except ValueError:
        await update.message.reply_text("السعر أو المدفوع لازم يكونوا أرقام فقط.")
        return

    remaining = price - paid
    today = date.today().isoformat()

    row = [
        data["name"],
        data["phone"],
        data["telegram"],
        price,
        paid,
        remaining,
        today,
        "",
    ]

    ws.append_row(row, value_input_option="USER_ENTERED")

    await update.message.reply_text(
        f"تم تسجيلك بنجاح ✅\n"
        f"المادة: {data['subject']}\n"
        f"المدفوع: {paid}\n"
        f"الباقي: {remaining}"
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Bot started, polling...")
    app.run_polling()


if __name__ == "__main__":
    main()

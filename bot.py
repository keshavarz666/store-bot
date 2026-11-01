import datetime
import http.server
import logging
import os
import threading
import libsql
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = "9176821719:AAE0qKhN8NKYM-QieqcLI4gqKUzCeecn_VA"

# اطلاعات دیتابیس ابری Turso شما
TURSO_URL = "libsql://storebotdb-keshavarz666.aws-eu-central-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTM1NTIyODcsImlkIjoiMDFhMTk4MGItOTAwMS03YmFhLTlmZWYtMjQwOWY5ZDNmZTJiIiwia2lkIjoiWEE2elBUMTVhNnVTcEdmY1lEc0VHSG9HQmpUOVpwaHRKOTRRaFQtcC04USIsInJpZCI6ImFjZDYzZmRiLTRjYTQtNGZjNS04YTdjLWZkMzhhZDE2OGU5NiJ9.HgN-ldBpLYtRga4O-IapgbWq-gDFltrz7bi_sunYlBqVlpRRU0lN32DetwGsInm4MTmTlthevda0Z4nR88CgAg"


def get_db_connection():
  return libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)


# لیست ادمین‌های ربات
ADMIN_IDS = {1605665646, 8037165419}
ADMIN_USERNAMES = {"rkeshavarz64", "alireza_rbn23"}


def is_admin_user(user):
  if not user:
    return False
  return user.id in ADMIN_IDS or (
      user.username
      and user.username.lower() in {u.lower() for u in ADMIN_USERNAMES}
  )


# Conversation States
(
    GET_PRODUCT,
    GET_SCENT,
    GET_PRODUCT_QTY,
    WAITING_CHECKOUT,
    GET_ORDER_PHONE,
    GET_ORDER_ADDRESS,
    GET_RECEIPT,
) = range(7)
GET_TRACK_QUERY = range(7, 8)
GET_SUPPORT_MSG, GET_SUPPORT_PHONE = range(8, 10)

CARD_NUMBER = "6219861078730941"
CARD_INFO = (
    f"💳 **شماره کارت جهت واریز وجه:**\n`{CARD_NUMBER}` (با زدن روی شماره کارت"
    " کپی میشود)\nبانک سامان - به نام علیرضا ربانی"
)


def normalize_phone(text):
  if not text:
    return ""
  p_digits = "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"
  e_digits = "01234567890123456789"
  return text.translate(str.maketrans(p_digits, e_digits)).strip()


def gregorian_to_jalali(gy, gm, gd):
  g_days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  if (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0):
    g_days_in_month[2] = 29
  gy -= 1600
  gm -= 1
  gd -= 1
  g_day_no = (
      365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
  )
  for i in range(gm):
    g_day_no += g_days_in_month[i + 1]
  g_day_no += gd
  j_day_no = g_day_no - 79
  j_np = j_day_no // 12053
  j_day_no %= 12053
  jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
  j_day_no %= 1461
  if j_day_no >= 365:
    jy += (j_day_no - 1) // 365
    j_day_no = (j_day_no - 1) % 365
  if j_day_no < 186:
    jm = 1 + j_day_no // 31
    jd = 1 + (j_day_no % 31)
  else:
    jm = 7 + (j_day_no - 186) // 30
    jd = 1 + ((j_day_no - 186) % 30)
  return jy, jm, jd


def format_persian_datetime(dt_str):
  if not dt_str:
    return ""
  try:
    if isinstance(dt_str, str):
      dt_str = dt_str.strip()
      dt = None
      for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
          dt = datetime.datetime.strptime(dt_str, fmt)
          break
        except ValueError:
          continue
        except Exception:
          pass
      if not dt:
        dt = datetime.datetime.fromisoformat(dt_str.replace(" ", "T"))
    else:
      dt = dt_str

    tehran_offset = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    if dt.tzinfo is None:
      dt_utc = dt.replace(tzinfo=datetime.timezone.utc)
      tehran_dt = dt_utc.astimezone(tehran_offset)
    else:
      tehran_dt = dt.astimezone(tehran_offset)

    jy, jm, jd = gregorian_to_jalali(
        tehran_dt.year, tehran_dt.month, tehran_dt.day
    )
    months = [
        "فروردین",
        "اردیبهشت",
        "خرداد",
        "تیر",
        "مرداد",
        "شهریور",
        "مهر",
        "آبان",
        "آذر",
        "دی",
        "بهمن",
        "اسفند",
    ]
    month_name = months[jm - 1]

    weekdays = {
        0: "دوشنبه",
        1: "سه‌شنبه",
        2: "چهارشنبه",
        3: "پنج‌شنبه",
        4: "جمعه",
        5: "شنبه",
        6: "یکشنبه",
    }
    day_name = weekdays[tehran_dt.weekday()]
    time_str = tehran_dt.strftime("%H:%M")

    e_digits = "0123456789"
    p_digits = "۰۱۲۳۴۵۶۷۸۹"
    trans = str.maketrans(e_digits, p_digits)

    p_jy = str(jy).translate(trans)
    p_jd = str(jd).translate(trans)
    p_time = time_str.translate(trans)

    return f"{day_name}، {p_jd} {month_name} {p_jy} - ساعت {p_time}"
  except Exception:
    return str(dt_str)


def init_db():
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY,"
      " first_name TEXT, username TEXT, joined_at TIMESTAMP DEFAULT"
      " CURRENT_TIMESTAMP)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS products (product_id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, name TEXT, original_price INTEGER, discount_price"
      " INTEGER)"
  )

  cursor.execute("SELECT COUNT(*) FROM products")
  if cursor.fetchone()[0] == 0:
    sample_products = [
        ("ایفل نی‌دار ۱۲۰ml", 490000, 444000),
        ("اسپری ۵۰۰ میل", 490000, 444000),
        ("آویزی", 360000, 333000),
    ]
    cursor.executemany(
        "INSERT INTO products (name, original_price, discount_price) VALUES"
        " (?, ?, ?)",
        sample_products,
    )

  cursor.execute(
      "CREATE TABLE IF NOT EXISTS orders (order_id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, user_id INTEGER, order_details TEXT, total_price"
      " INTEGER, phone TEXT, address TEXT, receipt_file_id TEXT, status TEXT"
      " DEFAULT 'در انتظار بررسی پرداخت', created_at TIMESTAMP DEFAULT"
      " CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(user_id))"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS support_requests (support_id INTEGER PRIMARY"
      " KEY AUTOINCREMENT, user_id INTEGER, message TEXT, phone TEXT,"
      " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN"
      " KEY(user_id) REFERENCES users(user_id))"
  )
  conn.commit()
  conn.close()


def save_user(user_id, first_name, username):
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?,"
      " ?, ?)",
      (user_id, first_name, username),
  )
  conn.commit()
  conn.close()


def save_order(user_id, order_details, total_price, phone, address, receipt_info):
  norm_phone = normalize_phone(phone)
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO orders (user_id, order_details, total_price, phone,"
      " address, receipt_file_id) VALUES (?, ?, ?, ?, ?, ?)",
      (user_id, order_details, total_price, norm_phone, address, receipt_info),
  )
  order_id = cursor.lastrowid
  conn.commit()
  conn.close()
  return order_id


def update_order_status(order_id, new_status):
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE orders SET status = ? WHERE order_id = ?",
      (new_status, order_id),
  )
  conn.commit()
  conn.close()


def save_support(user_id, message, phone=""):
  norm_phone = normalize_phone(phone)
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO support_requests (user_id, message, phone) VALUES (?, ?, ?)",
      (user_id, message, norm_phone),
  )
  last_id = cursor.lastrowid
  conn.commit()
  conn.close()
  return last_id


def update_support_phone(support_id, phone):
  norm_phone = normalize_phone(phone)
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE support_requests SET phone = ? WHERE support_id = ?",
      (norm_phone, support_id),
  )
  conn.commit()
  conn.close()


async def post_init(application):
  await application.bot.delete_my_commands()
  init_db()
  print("Database initialized successfully on Turso Cloud.")


def get_main_keyboard(is_admin=False):
  keyboard = [
      [InlineKeyboardButton("🛒 ثبت سفارش", callback_data="register_order")],
      [InlineKeyboardButton("📋 سفارش‌های من", callback_data="my_orders")],
      [InlineKeyboardButton("📦 پیگیری سفارش", callback_data="track_order")],
      [
          InlineKeyboardButton(
              "💬 ارتباط با کارشناسان و انتقادات", callback_data="support"
          )
      ],
      [InlineKeyboardButton("❌ خروج", callback_data="exit")],
  ]
  if is_admin:
    keyboard.insert(
        0,
        [InlineKeyboardButton("🛠 پنل مدیریت", callback_data="admin_panel_main")],
    )
  return InlineKeyboardMarkup(keyboard)


def get_reply_keyboard(is_admin=False):
  buttons = [[KeyboardButton("🏠 شروع مجدد (/start)")]]
  if is_admin:
    buttons.append([KeyboardButton("🛠 پنل مدیریت")])
  return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  save_user(user.id, user.first_name, user.username)
  is_admin = is_admin_user(user)

  welcome_text = (
      f"سلام {user.first_name} عزیز! 👋\n\n"
      "به ربات خدمات و فروشگاه ما خوش آمدید. 🌹\n"
      "لطفاً از منوی زیر یکی از گزینه‌های مورد نظر را انتخاب کنید:"
  )

  reply_markup = get_main_keyboard(is_admin)
  reply_kb = get_reply_keyboard(is_admin)

  if update.message:
    await update.message.reply_text(welcome_text, reply_markup=reply_kb)
    await update.message.reply_text(
        "منوی دسترسی سریع:", reply_markup=reply_markup
    )
  elif update.callback_query:
    await update.callback_query.message.reply_text(
        welcome_text, reply_markup=reply_kb
    )
    await update.callback_query.message.reply_text(
        "منوی دسترسی سریع:", reply_markup=reply_markup
    )


async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  context.user_data["cart"] = []

  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute("SELECT product_id, name FROM products")
  products = cursor.fetchall()
  conn.close()

  if not products:
    await query.edit_message_text(
        "📭 در حال حاضر کالایی موجود نمی‌باشد.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔙 بازگشت به منوی اصلی", callback_data="main_menu"
            )
        ]]),
    )
    return ConversationHandler.END

  keyboard = []
  for p in products:
    p_id, p_name = p
    keyboard.append(
        [InlineKeyboardButton(f"📦 {p_name}", callback_data=f"prod_{p_id}")]
    )
  keyboard.append(
      [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="main_menu")]
  )

  await query.edit_message_text(
      "🛒 **انتخاب کالا:**\n\nلطفاً کالای مورد نظر خود را انتخاب کنید:",
      parse_mode="Markdown",
      reply_markup=InlineKeyboardMarkup(keyboard),
  )
  return GET_PRODUCT


async def select_product_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.callback_query
  await query.answer()
  data = query.data

  if data == "main_menu":
    user = query.from_user
    is_admin = is_admin_user(user)
    await query.edit_message_text(
        "منوی اصلی:", reply_markup=get_main_keyboard(is_admin)
    )
    return ConversationHandler.END

  if data.startswith("prod_"):
    p_id = int(data.split("_")[1])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, original_price, discount_price FROM products WHERE"
        " product_id = ?",
        (p_id,),
    )
    prod = cursor.fetchone()
    conn.close()

    if not prod:
      await query.edit_message_text("کالای مورد نظر یافت نشد.")
      return ConversationHandler.END

    context.user_data["current_product"] = {
        "id": p_id,
        "name": prod[0],
        "orig_price": prod[1],
        "disc_price": prod[2],
    }

    scents = []
    if "ایفل" in prod[0]:
      scents = [
          "هلو",
          "بلک ارکید",
          "آدامس",
          "کاپیتان",
          "جنگل",
          "بلوبری",
          "پنبه",
          "لوندر",
          "جنگل بارانی",
          "فایر انجل",
          "ماه",
          "پودر",
          "انبه",
          "جلبک",
          "کول واتر",
          "قهوه",
          "اوشن",
      ]
    elif "اسپری" in prod[0]:
      scents = [
          "انبه",
          "انبه افریقایی",
          "کاپیتان",
          "قهوه",
          "کول واتر",
          "آنجل ملک",
          "پودر",
          "بوکت",
          "لوندر",
          "فایر آنجل",
          "جنگل",
          "پنبه",
          "بلوبری",
          "جلبک",
          "اکزوتیک",
          "هلو",
          "ماه",
          "اوشن",
      ]
    elif "آویزی" in prod[0]:
      scents = ["انبه", "لوندر", "جنگل", "آنجل ملک", "اقیانوس", "آدامس"]

    keyboard = []
    row = []
    for scent in scents:
      row.append(InlineKeyboardButton(scent, callback_data=f"scent_{scent}"))
      if len(row) == 3:
        keyboard.append(row)
        row = []
    if row:
      keyboard.append(row)

    keyboard.append(
        [InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]
    )

    await query.edit_message_text(
        f"📦 کالا: **{prod[0]}**\n\n🌸 لطفاً رایحه مورد نظر خود را انتخاب"
        " کنید:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return GET_SCENT


async def select_scent_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.callback_query
  await query.answer()
  data = query.data

  if data == "main_menu":
    user = query.from_user
    is_admin = is_admin_user(user)
    await query.edit_message_text(
        "منوی اصلی:", reply_markup=get_main_keyboard(is_admin)
    )
    return ConversationHandler.END

  if data.startswith("scent_"):
    scent_name = data.split("_", 1)[1]
    context.user_data["current_scent"] = scent_name

    current_prod = context.user_data.get("current_product")
    kb = [[InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")]]
    await query.edit_message_text(
        f"📦 کالا: **{current_prod['name']}**\n✨ رایحه: **{scent_name}**\n\nتعداد"
        " مورد نظر را به عدد وارد کنید:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return GET_PRODUCT_QTY


async def receive_product_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
  qty_text = update.message.text.strip()
  if not qty_text.isdigit() or int(qty_text) <= 0:
    await update.message.reply_text("لطفاً تعداد را به صورت عدد صحیح وارد کنید:")
    return GET_PRODUCT_QTY

  qty = int(qty_text)
  current_prod = context.user_data.get("current_product")
  current_scent = context.user_data.get("current_scent")

  item_orig_total = current_prod["orig_price"] * qty
  item_disc_total = current_prod["disc_price"] * qty

  context.user_data["cart"].append({
      "name": current_prod["name"],
      "scent": current_scent,
      "orig_price": current_prod["orig_price"],
      "disc_price": current_prod["disc_price"],
      "qty": qty,
      "orig_total": item_orig_total,
      "disc_total": item_disc_total,
  })

  cart = context.user_data["cart"]
  cart_summary = "🛒 **سبد خرید شما:**\n\n"
  grand_orig_total = 0
  grand_disc_total = 0

  for idx, item in enumerate(cart, 1):
    cart_summary += (
        f"{idx}. {item['name']} ({item['scent']}) - {item['qty']} عدد\n"
        f"   قیمت اصلی: ~{item['orig_total']:,}~ تومان\n"
        f"   قیمت با تخفیف: `{item['disc_total']:,}` تومان\n\n"
    )
    grand_orig_total += item["orig_total"]
    grand_disc_total += item["disc_total"]

  cart_summary += (
      f"💰 **جمع کل اصلی:** ~{grand_orig_total:,}~ تومان\n💰 **مجموع کل نهایی"
      f" (با تخفیف):** `{grand_disc_total:,} تومان`\n"
  )

  keyboard = [
      [InlineKeyboardButton("➕ افزودن کالای دیگر", callback_data="add_more")],
      [InlineKeyboardButton("🏁 پایان خرید و پرداخت", callback_data="checkout")],
  ]
  await update.message.reply_text(
      f"{cart_summary}\nچه کاری می‌خواهید انجام دهید؟",
      parse_mode="Markdown",
      reply_markup=InlineKeyboardMarkup(keyboard),
  )
  return WAITING_CHECKOUT


async def checkout_action_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.callback_query
  await query.answer()
  data = query.data

  if data == "add_more":
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, name FROM products")
    products = cursor.fetchall()
    conn.close()

    keyboard = []
    for p in products:
      p_id, p_name = p
      keyboard.append(
          [InlineKeyboardButton(f"📦 {p_name}", callback_data=f"prod_{p_id}")]
      )
    keyboard.append(
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="main_menu")]
    )

    await query.edit_message_text(
        "🛒 لطفاً کالای بعدی را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return GET_PRODUCT

  elif data == "checkout":
    await query.edit_message_text(
        "📞 لطفاً شماره تماس خود را برای ثبت سفارش ارسال کنید:"
    )
    return GET_ORDER_PHONE


async def receive_order_phone(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  phone = update.message.text.strip()
  context.user_data["order_phone"] = phone

  await update.message.reply_text("لطفاً آدرس خود را وارد کنید:")
  return GET_ORDER_ADDRESS


async def receive_order_address(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  address = update.message.text.strip()
  context.user_data["order_address"] = address

  cart = context.user_data.get("cart", [])
  grand_orig_total = sum(item["orig_total"] for item in cart)
  grand_disc_total = sum(item["disc_total"] for item in cart)
  context.user_data["grand_total"] = grand_disc_total

  invoice_text = "📋 **فاکتور نهایی سفارش:**\n\n"
  for idx, item in enumerate(cart, 1):
    invoice_text += (
        f"{idx}. {item['name']} (رایحه: {item['scent']}) | {item['qty']} عدد\n"
        f"   - قیمت هر واحد: ~{item['orig_price']:,}~ | با تخفیف:"
        f" `{item['disc_price']:,}` تومان\n"
        f"   - قیمت کل: ~{item['orig_total']:,}~ | کل با تخفیف:"
        f" `{item['disc_total']:,}` تومان\n\n"
    )

  invoice_text += (
      f"💰 **جمع کل فاکتور اصلی:** ~{grand_orig_total:,}~ تومان\n"
      f"🎁 **مجموع کل قابل پرداخت (با تخفیف):** `{grand_disc_total:,}`"
      " تومان\n\n"
  )
  invoice_text += f"{CARD_INFO}\n\n"
  invoice_text += (
      "📸 **لطفاً تصویر رسید واریز وجه را ارسال کنید:**\n(یا در صورت ارسال به"
      " صورت متن/فایل، آن را بفرستید)"
  )

  await update.message.reply_text(invoice_text, parse_mode="Markdown")
  return GET_RECEIPT


async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  cart = context.user_data.get("cart", [])
  grand_total = context.user_data.get("grand_total", 0)
  phone = context.user_data.get("order_phone", "")
  address = context.user_data.get("order_address", "")

  if not cart:
    await update.message.reply_text("سبد خرید خالی است.")
    return ConversationHandler.END

  receipt_info = ""
  if update.message.photo:
    receipt_info = f"photo:{update.message.photo[-1].file_id}"
  elif update.message.text:
    receipt_info = f"text:{update.message.text.strip()}"
  elif update.message.document:
    receipt_info = f"doc:{update.message.document.file_id}"

  order_details = " | ".join([
      f"{i['name']} ({i['scent']}) - {i['qty']} عدد (تخفیف‌خورده: {i['disc_total']:,} ت)"
      for i in cart
  ])
  order_id = save_order(
      user.id, order_details, grand_total, phone, address, receipt_info
  )

  admin_msg = (
      f"🚨 **سفارش جدید ثبت شد! (کد: {order_id})**\n\n"
      f"👤 مشتری: {user.first_name} (@{user.username if user.username else 'ندارد'})\n"
      f"📞 تلفن: `{phone}`\n"
      f"🏠 آدرس: {address}\n"
      f"📦 کالاها:\n{order_details}\n"
      f"💰 مبلغ کل: `{grand_total:,} تومان`"
  )

  for admin_id in ADMIN_IDS:
    try:
      if receipt_info.startswith("photo:"):
        await context.bot.send_photo(
            chat_id=admin_id,
            photo=receipt_info.replace("photo:", ""),
            caption=f"📸 **رسید پرداخت سفارش کد {order_id}**\n\n{admin_msg}",
            parse_mode="Markdown",
        )
      else:
        await context.bot.send_message(
            chat_id=admin_id, text=admin_msg, parse_mode="Markdown"
        )
        if receipt_info.startswith("text:"):
          await context.bot.send_message(
              chat_id=admin_id,
              text=f"📝 **متن رسید ارسال شده:**\n{receipt_info.replace('text:', '')}",
          )
    except Exception as e:
      logging.error(f"Error sending alert to admin {admin_id}: {e}")

  is_admin = is_admin_user(user)
  await update.message.reply_text(
      f"🎉 **سفارش شما با موفقیت ثبت شد!**\nکد پیگیری اختصاصی: `{order_id}`\nمبلغ"
      f" کل: `{grand_total:,} تومان`\nوضعیت: *در انتظار بررسی پرداخت*\n\nپس از"
      " بررسی رسید توسط مدیریت، سفارش شما تایید خواهد شد. 🙏",
      parse_mode="Markdown",
      reply_markup=get_main_keyboard(is_admin),
  )
  context.user_data["cart"] = []
  return ConversationHandler.END


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  is_admin = is_admin_user(user)
  context.user_data["cart"] = []
  await update.message.reply_text(
      "فرآیند لغو شد.", reply_markup=get_main_keyboard(is_admin)
  )
  return ConversationHandler.END


async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  user_id = update.effective_user.id
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT order_id, order_details, total_price, phone, address, status,"
      " created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC",
      (user_id,),
  )
  orders = cursor.fetchall()
  conn.close()
  if not orders:
    await query.edit_message_text(
        "سفارشی ثبت نکرده‌اید.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔙 بازگشت به منوی اصلی", callback_data="main_menu"
            )
        ]]),
    )
    return
  text = "📋 سفارش‌های شما (از جدیدترین):\n\n"
  for o in orders:
    p_date = format_persian_datetime(o[6])
    text += (
        f"کد پیگیری: `{o[0]}`\nجزئیات: {o[1]}\nمبلغ: {o[2]:,} تومان\nآدرس:"
        f" {o[4]}\nوضعیت: {o[5]}\nتاریخ: {p_date}\n------------------\n"
    )
  await query.edit_message_text(
      text,
      parse_mode="Markdown",
      reply_markup=InlineKeyboardMarkup([[
          InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")
      ]]),
  )


async def start_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  await query.edit_message_text("کد پیگیری یا شماره تماس خود را ارسال کنید:")
  return GET_TRACK_QUERY


async def receive_tracking_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  q_raw = update.message.text.strip()
  q_norm = normalize_phone(q_raw)
  user = update.effective_user
  is_admin = is_admin_user(user)
  conn = get_db_connection()
  cursor = conn.cursor()

  if q_raw.isdigit() or q_norm.isdigit():
    oid = int(q_norm) if q_norm.isdigit() else 0
    cursor.execute(
        "SELECT order_id, order_details, total_price, phone, address, status,"
        " created_at FROM orders WHERE order_id = ? OR phone LIKE ? OR phone"
        " LIKE ? ORDER BY created_at DESC",
        (oid, f"%{q_raw}%", f"%{q_norm}%"),
    )
  else:
    cursor.execute(
        "SELECT order_id, order_details, total_price, phone, address, status,"
        " created_at FROM orders WHERE phone LIKE ? OR phone LIKE ? ORDER BY"
        " created_at DESC",
        (f"%{q_raw}%", f"%{q_norm}%"),
    )
  orders = cursor.fetchall()
  conn.close()

  if not orders:
    await update.message.reply_text(
        "سفارشی یافت نشد.", reply_markup=get_main_keyboard(is_admin)
    )
    return ConversationHandler.END

  text = "📦 نتایج پیگیری:\n\n"
  for o in orders:
    p_date = format_persian_datetime(o[6])
    text += (
        f"کد: `{o[0]}`\nجزئیات: {o[1]}\nمبلغ: {o[2]:,} تومان\nآدرس:"
        f" {o[4]}\nوضعیت: {o[5]}\nتاریخ: {p_date}\n------------------\n"
    )
  await update.message.reply_text(
      text, parse_mode="Markdown", reply_markup=get_main_keyboard(is_admin)
  )
  return ConversationHandler.END


async def cancel_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  is_admin = is_admin_user(user)
  await update.message.reply_text(
      "لغو شد.", reply_markup=get_main_keyboard(is_admin)
  )
  return ConversationHandler.END


async def start_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  kb = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
  await query.edit_message_text(
      "💬 **ارتباط با کارشناسان و انتقادات**\n\nلطفاً پیام، پیشنهاد یا انتقاد خود"
      " را ارسال کنید:",
      parse_mode="Markdown",
      reply_markup=InlineKeyboardMarkup(kb),
  )
  return GET_SUPPORT_MSG


async def receive_support_msg(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  user = update.effective_user
  msg = update.message.text.strip()

  support_id = save_support(user.id, msg, phone="")
  context.user_data["current_support_id"] = support_id

  kb = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
  await update.message.reply_text(
      "✅ پیام شما ثبت شد.\n\nدر صورت تمایل می‌توانید شماره تماس خود را بفرستید"
      " (یا برای صرف‌نظر کلمه 'ندارم' یا '-' را ارسال کنید):",
      reply_markup=InlineKeyboardMarkup(kb),
  )
  return GET_SUPPORT_PHONE


async def receive_support_phone(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  user = update.effective_user
  phone_text = update.message.text.strip()
  support_id = context.user_data.get("current_support_id")

  if support_id and phone_text not in ["ندارم", "-", "هیچکدام"]:
    update_support_phone(support_id, phone_text)

  is_admin = is_admin_user(user)
  await update.message.reply_text(
      "🙏 با تشکر از اطلاعات پرداختی/تماسی شما.",
      reply_markup=get_main_keyboard(is_admin),
  )
  return ConversationHandler.END


async def cancel_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  is_admin = is_admin_user(user)
  await update.message.reply_text(
      "لغو شد.", reply_markup=get_main_keyboard(is_admin)
  )
  return ConversationHandler.END


async def admin_panel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = (
      update.effective_user
      if update.effective_user
      else update.callback_query.from_user
  )
  if not is_admin_user(user):
    if update.message:
      await update.message.reply_text("دسترسی ندارید.")
    elif update.callback_query:
      await update.callback_query.answer("دسترسی ندارید.", show_alert=True)
    return

  kb = [
      [
          InlineKeyboardButton(
              "📦 مدیریت سفارش‌ها (فیلتر وضعیت)",
              callback_data="admin_orders_menu",
          )
      ],
      [
          InlineKeyboardButton(
              "💬 لیست پیام‌ها و نظرات", callback_data="admin_supports"
          )
      ],
      [
          InlineKeyboardButton(
              "🔙 بازگشت به منوی اصلی", callback_data="main_menu"
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(kb)
  text = (
      "🛠 **پنل مدیریت پیشرفته**\n\nلطفاً یکی از بخش‌های زیر را انتخاب کنید:"
  )

  if update.message:
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=reply_markup
    )
  elif update.callback_query:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=reply_markup
    )


async def admin_orders_filter_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.callback_query
  await query.answer()

  kb = [
      [
          InlineKeyboardButton(
              "⏳ در انتظار پرداخت",
              callback_data="admin_filter_در انتظار بررسی پرداخت",
          ),
          InlineKeyboardButton(
              "📞 تماس گرفته شد",
              callback_data="admin_filter_با مشتری تماس گرفته شد",
          ),
      ],
      [
          InlineKeyboardButton(
              "✅ تایید شد", callback_data="admin_filter_سفارش تایید شد"
          ),
          InlineKeyboardButton(
              "❌ کنسل شد", callback_data="admin_filter_سفارش کنسل شد"
          ),
      ],
      [
          InlineKeyboardButton(
              "🚚 ارسال شد", callback_data="admin_filter_سفارش ارسال شد"
          ),
          InlineKeyboardButton(
              "🏠 تحویل داده شد",
              callback_data="admin_filter_سفارش تحویل داده شد",
          ),
      ],
      [InlineKeyboardButton("📋 همه سفارش‌ها", callback_data="admin_filter_all")],
      [
          InlineKeyboardButton(
              "🔙 بازگشت به منوی مدیریت", callback_data="admin_panel_back"
          )
      ],
  ]
  await query.edit_message_text(
      "لطفاً وضعیت سفارش مورد نظر را انتخاب کنید:",
      reply_markup=InlineKeyboardMarkup(kb),
  )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  data = query.data

  if data == "admin_panel_main":
    await admin_panel_menu(update, context)

  elif data == "admin_panel_back":
    await admin_panel_menu(update, context)

  elif data == "admin_orders_menu":
    await admin_orders_filter_menu(update, context)

  elif data == "admin_supports":
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT S.message, S.phone, U.first_name, U.username, S.created_at FROM"
        " support_requests S JOIN users U ON S.user_id = U.user_id ORDER BY"
        " S.created_at DESC LIMIT 15"
    )
    items = cursor.fetchall()
    conn.close()

    if not items:
      await query.edit_message_text(
          "📭 هیچ پیامی ثبت نشده است.",
          reply_markup=InlineKeyboardMarkup([[
              InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel_back")
          ]]),
      )
      return

    text = "💬 **لیست پیام‌ها و نظرات کاربران:**\n\n"
    for item in items:
      msg, phone, fname, uname, date = item
      uname_str = f"(@{uname})" if uname else ""
      phone_str = f" | تلفن: {phone}" if phone else " | تلفن: ثبت نشده"
      p_date = format_persian_datetime(date)
      text += (
          f"👤 {fname} {uname_str}{phone_str}\n💬 {msg}\n⏱"
          f" {p_date}\n------------------\n"
      )

    kb = [[
        InlineKeyboardButton(
            "🔙 بازگشت به پنل مدیریت", callback_data="admin_panel_back"
        )
    ]]
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
    )

  elif data.startswith("admin_filter_"):
    status_filter = data.replace("admin_filter_", "", 1)
    conn = get_db_connection()
    cursor = conn.cursor()
    if status_filter == "all":
      cursor.execute(
          "SELECT O.order_id, U.first_name, U.username, O.order_details,"
          " O.total_price, O.phone, O.address, O.receipt_file_id, O.status,"
          " O.created_at FROM orders O JOIN users U ON O.user_id = U.user_id"
          " ORDER BY O.created_at DESC LIMIT 10"
      )
    else:
      cursor.execute(
          "SELECT O.order_id, U.first_name, U.username, O.order_details,"
          " O.total_price, O.phone, O.address, O.receipt_file_id, O.status,"
          " O.created_at FROM orders O JOIN users U ON O.user_id = U.user_id"
          " WHERE O.status = ? ORDER BY O.created_at DESC LIMIT 10",
          (status_filter,),
      )
    orders = cursor.fetchall()
    conn.close()

    if not orders:
      kb = [[
          InlineKeyboardButton(
              "🔙 بازگشت به منوی مدیریت", callback_data="admin_panel_back"
          )
      ]]
      await query.edit_message_text(
          "سفارشی با این وضعیت یافت نشد.", reply_markup=InlineKeyboardMarkup(kb)
      )
      return

    await query.edit_message_text(
        f"لیست سفارش‌ها (فیلتر: {status_filter if status_filter != 'all' else 'همه'}):"
    )

    for o in orders:
      p_date = format_persian_datetime(o[9])
      receipt_info = o[7] if o[7] else "ثبت نشده"
      text = (
          f"کد: `{o[0]}` | مشتری: {o[1]} (@{o[2] if o[2] else 'ندارد'})\nکالاها:"
          f" {o[3]}\nمبلغ: {o[4]:,} تومان\nتلفن: {o[5]}\nآدرس: {o[6]}\nوضعیت:"
          f" {o[8]}\nتاریخ: {p_date}"
      )
      kb = [
          [
              InlineKeyboardButton(
                  "بررسی", callback_data=f"setstat_{o[0]}_در حال بررسی"
              ),
              InlineKeyboardButton(
                  "تماس", callback_data=f"setstat_{o[0]}_با مشتری تماس گرفته شد"
              ),
          ],
          [
              InlineKeyboardButton(
                  "تایید", callback_data=f"setstat_{o[0]}_سفارش تایید شد"
              ),
              InlineKeyboardButton(
                  "کنسل", callback_data=f"setstat_{o[0]}_سفارش کنسل شد"
              ),
          ],
          [
              InlineKeyboardButton(
                  "ارسال", callback_data=f"setstat_{o[0]}_سفارش ارسال شد"
              ),
              InlineKeyboardButton(
                  "تحویل", callback_data=f"setstat_{o[0]}_سفارش تحویل داده شد"
              ),
          ],
      ]
      await query.message.reply_text(
          text, reply_markup=InlineKeyboardMarkup(kb)
      )

      if receipt_info.startswith("photo:"):
        try:
          await query.message.reply_photo(
              photo=receipt_info.replace("photo:", ""),
              caption=f"📸 رسید ارسال‌شده برای سفارش `{o[0]}`",
              parse_mode="Markdown",
          )
        except Exception:
          pass
      elif receipt_info.startswith("text:"):
        await query.message.reply_text(
            f"📝 **متن رسید ارسال‌شده برای سفارش `{o[0]}`:**\n{receipt_info.replace('text:', '')}",
            parse_mode="Markdown",
        )

    kb_back = [[
        InlineKeyboardButton(
            "🔙 بازگشت به پنل مدیریت", callback_data="admin_panel_back"
        )
    ]]
    await query.message.reply_text(
        "پایان لیست سفارش‌ها.",
        reply_markup=InlineKeyboardMarkup(kb_back),
    )

  elif data.startswith("setstat_"):
    _, oid, st = data.split("_", 2)
    update_order_status(int(oid), st)

    kb_back = [[
        InlineKeyboardButton(
            "🔙 بازگشت به منوی مدیریت", callback_data="admin_panel_back"
        )
    ]]
    await query.edit_message_text(
        f"✅ وضعیت سفارش کد `{oid}` به **{st}** تغییر یافت.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb_back),
    )

  elif data == "main_menu":
    user = query.from_user
    is_admin = is_admin_user(user)
    await query.edit_message_text(
        "منوی اصلی:", reply_markup=get_main_keyboard(is_admin)
    )

  elif data == "exit":
    await query.message.delete()


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
  txt = update.message.text
  user = update.effective_user
  is_admin = is_admin_user(user)

  if "شروع مجدد" in txt or "/start" in txt:
    await start(update, context)
  elif "پنل مدیریت" in txt and is_admin:
    await admin_panel_menu(update, context)


def run_dummy_server():
  port = int(os.environ.get("PORT", 10000))
  server_address = ("", port)
  httpd = http.server.HTTPServer(
      server_address, http.server.SimpleHTTPRequestHandler
  )
  print(f"Dummy web server running on port {port}")
  httpd.serve_forever()


def main():
  threading.Thread(target=run_dummy_server, daemon=True).start()

  application = (
      ApplicationBuilder().token(TOKEN).post_init(post_init).build()
  )

  order_conv = ConversationHandler(
      entry_points=[
          CallbackQueryHandler(start_order, pattern="^register_order$")
      ],
      states={
          GET_PRODUCT: [
              CallbackQueryHandler(
                  select_product_callback, pattern="^(prod_|main_menu)"
              )
          ],
          GET_SCENT: [
              CallbackQueryHandler(
                  select_scent_callback, pattern="^(scent_|main_menu)"
              )
          ],
          GET_PRODUCT_QTY: [
              MessageHandler(filters.TEXT & ~filters.COMMAND, receive_product_qty)
          ],
          WAITING_CHECKOUT: [
              CallbackQueryHandler(
                  checkout_action_handler, pattern="^(add_more|checkout)$"
              )
          ],
          GET_ORDER_PHONE: [
              MessageHandler(
                  filters.TEXT & ~filters.COMMAND, receive_order_phone
              )
          ],
          GET_ORDER_ADDRESS: [
              MessageHandler(
                  filters.TEXT & ~filters.COMMAND, receive_order_address
              )
          ],
          GET_RECEIPT: [
              MessageHandler(
                  (filters.TEXT | filters.PHOTO | filters.Document.ALL)
                  & ~filters.COMMAND,
                  receive_receipt,
              )
          ],
      },
      fallbacks=[CommandHandler("cancel", cancel_order)],
      per_message=False,
  )

  track_conv = ConversationHandler(
      entry_points=[
          CallbackQueryHandler(start_tracking, pattern="^track_order$")
      ],
      states={
          GET_TRACK_QUERY: [
              MessageHandler(
                  filters.TEXT & ~filters.COMMAND, receive_tracking_query
              )
          ],
      },
      fallbacks=[CommandHandler("cancel", cancel_tracking)],
      per_message=False,
  )

  support_conv = ConversationHandler(
      entry_points=[CallbackQueryHandler(start_support, pattern="^support$")],
      states={
          GET_SUPPORT_MSG: [
              MessageHandler(
                  filters.TEXT & ~filters.COMMAND, receive_support_msg
    )
          ],
          GET_SUPPORT_PHONE: [
              MessageHandler(
                  filters.TEXT & ~filters.COMMAND, receive_support_phone
              )
          ],
      },
      fallbacks=[CommandHandler("cancel", cancel_support)],
      per_message=False,
  )

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CommandHandler("admin", admin_panel_menu))
  application.add_handler(order_conv)
  application.add_handler(track_conv)
  application.add_handler(support_conv)
  application.add_handler(
      CallbackQueryHandler(show_my_orders, pattern="^my_orders$")
  )
  application.add_handler(
      MessageHandler(filters.TEXT & ~filters.COMMAND, text_router)
  )
  application.add_handler(CallbackQueryHandler(button_handler))

  print("Bot is starting polling...")
  application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
  main()


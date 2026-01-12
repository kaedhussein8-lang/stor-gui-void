import telebot
import time
import json
import base64
from pathlib import Path
from telebot import types
import datetime

# ===== الإعدادات =====
TOKEN = "8415470144:AAGHmXHK-ZuxjsibOyb4OGq4817OJrHx-aA"
OWNER_ID = 7421255692  # ايدي الأدمن
DATA_FILE = "bot_data.json"
SIGNAL_FILE = "signals.log"

bot = telebot.TeleBot(TOKEN)

# ===== تحميل البيانات =====
data_path = Path(DATA_FILE)
if data_path.exists():
    with open(DATA_FILE, "r", encoding="utf8") as f:
        data = json.load(f)
else:
    data = {"users": {}}

offers_list = []

def save():
    with open(DATA_FILE, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False)

# ===== إصلاح البيانات القديمة =====
def ensure_user(uid):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"coins":0,"invited_by":None,"invites":0}
    else:
        user = data["users"][uid]
        if "coins" not in user: user["coins"] = 0
        if "invited_by" not in user: user["invited_by"] = None
        if "invites" not in user: user["invites"] = 0
    return data["users"][uid]

# ===== دالة تسجيل الأحداث =====
def notify_signal(event_text):
    timestamp = datetime.datetime.now().isoformat()
    raw = f"{timestamp} | {event_text}"
    encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    with open(SIGNAL_FILE, "a", encoding="utf-8") as f:
        f.write(encoded + "\n")

# ===== لوحات =====
def main_keyboard(uid):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎁 العروض", callback_data="offers"))
    kb.add(types.InlineKeyboardButton("🔗 رابط الدعوة", callback_data="invite"))
    kb.add(types.InlineKeyboardButton("🔁 تحويل كوينز", callback_data="start_transfer"))
    if uid == OWNER_ID:
        kb.add(types.InlineKeyboardButton("⚙️ لوحة الأدمن", callback_data="admin_panel"))
    return kb

def offers_keyboard():
    kb = types.InlineKeyboardMarkup()
    for i, o in enumerate(offers_list):
        if not o.get("claimed", False):
            kb.add(types.InlineKeyboardButton(
                f"{o['name']} - {o['price']} كوينز 🪙 ({o['reward']['type'] if o.get('reward') else 0})",
                callback_data=f"buy_offer_{i}"
            ))
    if not any(not o.get("claimed", False) for o in offers_list):
        kb.add(types.InlineKeyboardButton("لا توجد عروض 😔", callback_data="none"))
    return kb

def admin_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ إضافة عرض", callback_data="admin_add"))
    kb.add(types.InlineKeyboardButton("🗑 حذف عرض", callback_data="admin_delete"))
    kb.add(types.InlineKeyboardButton("📋 عرض العروض", callback_data="admin_list"))
    kb.add(types.InlineKeyboardButton("💰 زيادة كوينز لمستخدم", callback_data="admin_add_coins"))
    kb.add(types.InlineKeyboardButton("🔻 خصم كوينز من مستخدم", callback_data="admin_sub_coins"))
    kb.add(types.InlineKeyboardButton("⬅ رجوع", callback_data="back_main"))
    return kb

# ===== /start + الدعوة =====
@bot.message_handler(commands=["start"])
def start(m):
    uid = m.from_user.id
    user = ensure_user(uid)
    notify_signal(f"START | user_id={uid} | username=@{m.from_user.username} | name={m.from_user.first_name}")

    # نظام الدعوة
    if m.text.startswith("/start "):
        inviter = m.text.split()[1]
        if inviter.isdigit():
            inviter = int(inviter)
            if user["invited_by"] is None and inviter != uid:
                inviter_user = ensure_user(inviter)
                inviter_user["coins"] += 10
                inviter_user["invites"] += 1
                user["invited_by"] = inviter
                save()
                notify_signal(f"INVITE | inviter={inviter} | new_user={uid}")

    invite_link = f"https://t.me/{bot.get_me().username}?start={uid}"
    bot.send_message(m.chat.id,
                     f"أهلاً {m.from_user.first_name} 👋\nرصيدك: {user['coins']} كوينز 🪙\nدعواتك: {user['invites']}\n\n🔗 رابطك:\n{invite_link}",
                     reply_markup=main_keyboard(uid))

# ===== Callback =====
@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id
    user = ensure_user(uid)

    if c.data == "offers":
        bot.edit_message_text("🎁 العروض المتاحة:", c.message.chat.id, c.message.message_id, reply_markup=offers_keyboard())

    elif c.data.startswith("buy_offer_"):
        i = int(c.data.split("_")[-1])
        offer = offers_list[i]

        if offer.get("claimed", False):
            bot.answer_callback_query(c.id, "العرض غير متاح")
            return
        if user["coins"] < offer["price"]:
            bot.answer_callback_query(c.id, "كوينزك غير كافية")
            return

        user["coins"] -= offer["price"]
        offer["claimed"] = True
        offer["buyer"] = uid
        save()
        notify_signal(f"BUY | user_id={uid} | offer={offer['name']}")

        # إرسال المكافأة
        reward = offer.get("reward", {})
        if reward:
            if reward["type"] == "text":
                bot.send_message(c.message.chat.id, reward["content"])
            elif reward["type"] == "photo":
                bot.send_photo(c.message.chat.id, reward["file_id"], caption=reward.get("caption"))
            elif reward["type"] == "document":
                bot.send_document(c.message.chat.id, reward["file_id"], caption=reward.get("filename"))
            elif reward["type"] == "video":
                bot.send_video(c.message.chat.id, reward["file_id"], caption=reward.get("caption"))

        bot.answer_callback_query(c.id, "✅ تم الشراء")
        bot.send_message(c.message.chat.id, f"🎉 اشتريت العرض: {offer['name']}")

    elif c.data == "invite":
        link = f"https://t.me/{bot.get_me().username}?start={uid}"
        bot.send_message(c.message.chat.id, f"🔗 رابط دعوتك:\n{link}")

    elif c.data == "start_transfer":
        msg = bot.send_message(c.message.chat.id, "اكتب التحويل بهذا الشكل:\nتحويل user_id الكمية")
        bot.register_next_step_handler(msg, transfer_step)

    # ===== لوحة الأدمن =====
    elif c.data == "admin_panel" and uid == OWNER_ID:
        bot.edit_message_text("⚙️ لوحة تحكم الأدمن", c.message.chat.id, c.message.message_id, reply_markup=admin_keyboard())

    elif c.data == "admin_add" and uid == OWNER_ID:
        msg = bot.send_message(c.message.chat.id, "اكتب العرض هكذا:\nاسم العرض | السعر")
        bot.register_next_step_handler(msg, admin_add_reward_prompt)

    elif c.data == "admin_list" and uid == OWNER_ID:
        if not offers_list:
            bot.send_message(c.message.chat.id, "لا توجد عروض")
            return
        text = "📋 العروض:\n\n"
        for i, o in enumerate(offers_list):
            status = "❌ محجوز" if o.get("claimed", False) else "✅ متاح"
            reward_type = o.get("reward", {}).get("type", "0")
            text += f"{i+1}- {o['name']} | {o['price']} كوينز | مكافأة: {reward_type} | {status}\n"
        bot.send_message(c.message.chat.id, text)

    elif c.data == "admin_delete" and uid == OWNER_ID:
        kb = types.InlineKeyboardMarkup()
        for i, o in enumerate(offers_list):
            kb.add(types.InlineKeyboardButton(o['name'], callback_data=f"del_{i}"))
        bot.send_message(c.message.chat.id, "اختر عرض للحذف:", reply_markup=kb)

    elif c.data.startswith("del_") and uid == OWNER_ID:
        i = int(c.data.split("_")[-1])
        deleted = offers_list.pop(i)
        save()
        bot.answer_callback_query(c.id, "🗑 تم الحذف")
        bot.send_message(c.message.chat.id, f"تم حذف العرض: {deleted['name']}")

    # زيادة كوينز
    elif c.data == "admin_add_coins" and uid == OWNER_ID:
        msg = bot.send_message(c.message.chat.id, "اكتب هكذا:\nuser_id | كمية الزيادة")
        bot.register_next_step_handler(msg, admin_add_coins_step)

    # خصم كوينز
    elif c.data == "admin_sub_coins" and uid == OWNER_ID:
        msg = bot.send_message(c.message.chat.id, "اكتب هكذا:\nuser_id | كمية الخصم")
        bot.register_next_step_handler(msg, admin_sub_coins_step)

    elif c.data == "back_main":
        bot.edit_message_text("القائمة الرئيسية", c.message.chat.id, c.message.message_id, reply_markup=main_keyboard(uid))

# ===== خطوات إضافة العرض مع أي مكافأة =====
def admin_add_reward_prompt(m):
    if m.from_user.id != OWNER_ID:
        return
    try:
        parts = m.text.split("|")
        name = parts[0].strip()
        price = int(parts[1].strip())
        data["_temp_offer"] = {"name": name, "price": price}
    except:
        bot.send_message(m.chat.id, "❌ صيغة خاطئة، يجب: اسم العرض | السعر")
        return

    msg = bot.send_message(m.chat.id, "الآن أرسل المكافأة: نص، صورة، ملف، فيديو ... أي شيء")
    bot.register_next_step_handler(msg, admin_add_reward_step_any)

def admin_add_reward_step_any(m):
    if m.from_user.id != OWNER_ID:
        return

    temp = data.get("_temp_offer", {})
    if not temp:
        bot.send_message(m.chat.id, "❌ خطأ: بيانات العرض غير موجودة")
        return

    reward_data = {}
    if m.content_type == "text":
        reward_data = {"type": "text", "content": m.text}
    elif m.content_type == "photo":
        file_id = m.photo[-1].file_id
        reward_data = {"type": "photo", "file_id": file_id, "caption": m.caption}
    elif m.content_type == "document":
        reward_data = {"type": "document", "file_id": m.document.file_id, "filename": m.document.file_name}
    elif m.content_type == "video":
        reward_data = {"type": "video", "file_id": m.video.file_id, "caption": m.caption}
    else:
        bot.send_message(m.chat.id, "❌ نوع المكافأة غير مدعوم")
        return

    offer = {"name": temp["name"], "price": temp["price"], "reward": reward_data, "claimed": False}
    offers_list.append(offer)
    save()
    data.pop("_temp_offer", None)

    bot.send_message(m.chat.id, f"✅ تم إضافة العرض:\nاسم: {offer['name']}\nالسعر: {offer['price']}\nنوع المكافأة: {reward_data['type']}")
    notify_signal(f"ADMIN_ADD | offer={offer['name']} | price={offer['price']} | reward_type={reward_data['type']}")

# ===== تحويل =====
def transfer_step(m):
    try:
        _, to_id, amount = m.text.split()
        to_id = str(int(to_id))
        amount = int(amount)
    except:
        bot.send_message(m.chat.id, "صيغة خاطئة")
        return

    from_user = ensure_user(m.from_user.id)
    if amount <= 0 or from_user["coins"] < amount:
        bot.send_message(m.chat.id, "كوينز غير كافية")
        return

    to_user = ensure_user(to_id)
    from_user["coins"] -= amount
    to_user["coins"] += amount
    save()
    notify_signal(f"TRANSFER | from={m.from_user.id} | to={to_id} | amount={amount}")
    bot.send_message(m.chat.id, f"تم تحويل {amount} كوينز 🪙")

# ===== خطوات زيادة/خصم الكوينز =====
def admin_add_coins_step(m):
    if m.from_user.id != OWNER_ID:
        return
    try:
        uid_target, amount = m.text.split("|")
        uid_target = str(int(uid_target.strip()))
        amount = int(amount.strip())
    except:
        bot.send_message(m.chat.id, "❌ صيغة خاطئة")
        return
    user_target = ensure_user(uid_target)
    user_target["coins"] += amount
    save()
    bot.send_message(m.chat.id, f"✅ تم إضافة {amount} كوينز للمستخدم {uid_target}")
    notify_signal(f"ADMIN_ADD_COINS | to={uid_target} | amount={amount}")

def admin_sub_coins_step(m):
    if m.from_user.id != OWNER_ID:
        return
    try:
        uid_target, amount = m.text.split("|")
        uid_target = str(int(uid_target.strip()))
        amount = int(amount.strip())
    except:
        bot.send_message(m.chat.id, "❌ صيغة خاطئة")
        return
    user_target = ensure_user(uid_target)
    user_target["coins"] = max(0, user_target["coins"] - amount)
    save()
    bot.send_message(m.chat.id, f"✅ تم خصم {amount} كوينز من المستخدم {uid_target}")
    notify_signal(f"ADMIN_SUB_COINS | to={uid_target} | amount={amount}")

# ===== تشغيل البوت =====
bot.infinity_polling()
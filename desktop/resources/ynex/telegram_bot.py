"""
Y·NEX Telegram Bot
全球通用遥控器，通过 Bot 实现随时随地唤醒和控制。

使用方法：
1. 在 Telegram 搜索 @BotFather，创建 Bot，获取 Token
2. 在 .env 中设置 TELEGRAM_BOT_TOKEN
3. 运行 python main.py（或 python telegram_bot.py 单独启动）

权限映射：
- /owner <key_hash> - 将用户升级为 owner（首次配置用）
- /chat <文本> - 与Y·NEX对话
- /status - 系统状态
- /devices - 设备列表
- /rules - 自动化规则
- /help - 帮助
"""

import os
import threading
from typing import Optional

from logger import logger

_bot_instance = None
_bot_thread = None


def _get_bot_token() -> str:
    from config import settings
    return settings.telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")


def _is_enabled() -> bool:
    return bool(_get_bot_token())


def start_bot():
    """在后台线程中启动 Telegram Bot"""
    global _bot_instance, _bot_thread
    if not _is_enabled():
        logger.warning("Telegram Bot 未配置，跳过启动（设置 TELEGRAM_BOT_TOKEN 启用）")
        return

    if _bot_instance is not None:
        logger.info("Telegram Bot 已运行")
        return

    _bot_thread = threading.Thread(target=_run_bot, daemon=True, name="telegram-bot")
    _bot_thread.start()


def _run_bot():
    """Bot 主循环"""
    import telegram
    from telegram import Update
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        filters, ContextTypes, ConversationHandler
    )
    from auth import verify_request, create_api_key, UserRole
    from brain import get_ai_response
    from device_hub import list_domains, parse_and_execute
    from automation_engine import list_rules
    from speech import speak

    token = _get_bot_token()
    app = Application.builder().token(token).build()

    # 维护用户角色映射（telegram_user_id -> role）
    # 持久化到 data/telegram_users.json
    _user_roles = _load_telegram_users()

    def _save_user_roles():
        import json
        os.makedirs("data", exist_ok=True)
        with open("data/telegram_users.json", "w", encoding="utf-8") as f:
            json.dump(_user_roles, f, ensure_ascii=False)

    def _get_role(update: Update) -> UserRole:
        uid = str(update.effective_user.id)
        role_str = _user_roles.get(uid, "guest")
        return UserRole(role_str)

    # ---- 命令处理器 ----

    async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 Y·NEX AI 管家\n\n"
            "/chat <文本> - 与Y·NEX对话\n"
            "/status - 系统状态\n"
            "/devices - 设备列表\n"
            "/rules - 自动化规则\n"
            "/help - 帮助\n\n"
            "⚠️ 当前为 guest 权限，使用 /owner <密钥> 认证可解锁全部功能。"
        )

    async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        role = _get_role(update)
        await update.message.reply_text(
            f"🔐 当前权限：{role.value}\n\n"
            "/chat <文本> - 对话（owner/family/guest）\n"
            "/status - 系统状态（owner/family）\n"
            "/devices - 设备列表（owner/family）\n"
            "/wake <消息> - 远程唤醒（owner/family）\n"
            "/do <指令> - 执行设备指令（owner/family）\n"
            "/owner <key_hash> - 认证为 owner\n"
            "/help - 显示此帮助"
        )

    async def cmd_owner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """设置 owner 权限（通过 key_hash 验证）"""
        uid = str(update.effective_user.id)
        if len(ctx.args) < 1:
            await update.message.reply_text("用法：/owner <密钥>")
            return
        # 此处简化：提供 owner API key 的前8位即可升级
        provided = ctx.args[0].strip()
        # 验证逻辑：通过 list_api_keys 比对
        from auth import list_api_keys
        keys = list_api_keys()
        matched = [k for k in keys if k["id"] == provided and k["role"] == "owner"]
        if matched:
            _user_roles[uid] = "owner"
            _save_user_roles()
            await update.message.reply_text(f"✅ 已认证为 owner。欢迎，先生。")
            logger.info(f"Telegram 用户 {uid} 升级为 owner")
        else:
            await update.message.reply_text("❌ 密钥无效或非 owner 级别。")

    async def cmd_chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        role = _get_role(update)
        if not ctx.args:
            await update.message.reply_text("用法：/chat <文本>")
            return
        text = " ".join(ctx.args)
        # 如果是 owner/family，使用真实 LLM
        use_mock = (role == UserRole.GUEST)
        try:
            reply = get_ai_response(text, use_mock=use_mock)
            await update.message.reply_text(f"👤 {update.effective_user.first_name}（{role.value}）\n\n{reply}")
        except Exception as e:
            logger.error(f"Telegram chat error: {e}")
            await update.message.reply_text(f"处理失败：{e}")

    async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        role = _get_role(update)
        if role == UserRole.GUEST:
            await update.message.reply_text("⚠️ 权限不足")
            return
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            uptime_s = time.time() - psutil.boot_time()
            h, m = int(uptime_s // 3600), int((uptime_s % 3600) // 60)
            await update.message.reply_text(
                f"🖥️ 系统状态\n\n"
                f"CPU：{cpu:.1f}%\n"
                f"内存：{mem.percent:.1f}%\n"
                f"磁盘：{disk.percent:.1f}%\n"
                f"运行时长：{h}h {m}m"
            )
        except Exception as e:
            await update.message.reply_text(f"获取状态失败：{e}")

    async def cmd_devices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        role = _get_role(update)
        if role == UserRole.GUEST:
            await update.message.reply_text("⚠️ 权限不足")
            return
        domains = list_domains()
        await update.message.reply_text(f"📡 设备域：\n{domains}")

    async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        role = _get_role(update)
        if role == UserRole.GUEST:
            await update.message.reply_text("⚠️ 权限不足")
            return
        rules = list_rules()
        await update.message.reply_text(f"⚙️ 自动化规则：\n{rules}")

    async def cmd_wake(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        role = _get_role(update)
        if role == UserRole.GUEST:
            await update.message.reply_text("⚠️ 权限不足")
            return
        msg = " ".join(ctx.args) if ctx.args else "先生，我在这里。"
        try:
            speak(msg)
            await update.message.reply_text(f"🔔 已唤醒：{msg}")
        except Exception as e:
            await update.message.reply_text(f"唤醒失败：{e}")

    async def cmd_do(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """直接执行设备指令"""
        role = _get_role(update)
        if role == UserRole.GUEST:
            await update.message.reply_text("⚠️ 权限不足")
            return
        if not ctx.args:
            await update.message.reply_text("用法：/do <指令>，如 /do pc.activate.Notepad")
            return
        cmd = " ".join(ctx.args)
        try:
            result = parse_and_execute(cmd)
            await update.message.reply_text(f"✅ {result}")
        except Exception as e:
            await update.message.reply_text(f"执行失败：{e}")

    async def cmd_addkey(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Owner 专用：创建新的 API Key"""
        role = _get_role(update)
        if role != UserRole.OWNER:
            await update.message.reply_text("⚠️ 仅 owner 可执行此操作")
            return
        if len(ctx.args) < 2:
            await update.message.reply_text("用法：/addkey <名称> <owner|family|guest>")
            return
        name = ctx.args[0]
        role_str = ctx.args[1]
        try:
            from auth import create_api_key as _create, UserRole as UR
            raw, key_id = _create(name, UR(role_str))
            await update.message.reply_text(
                f"✅ 已创建 API Key\n"
                f"名称：{name}\n"
                f"角色：{role_str}\n"
                f"Key：{raw}\n\n"
                f"⚠️ 仅显示一次，请妥善保存！"
            )
        except Exception as e:
            await update.message.reply_text(f"创建失败：{e}")

    async def echo_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """未匹配命令的文本全部当对话处理"""
        role = _get_role(update)
        text = update.message.text
        use_mock = (role == UserRole.GUEST)
        try:
            reply = get_ai_response(text, use_mock=use_mock)
            await update.message.reply_text(reply)
        except Exception as e:
            await update.message.reply_text(f"处理失败：{e}")

    # ---- 注册处理器 ----
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("owner", cmd_owner))
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("devices", cmd_devices))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("wake", cmd_wake))
    app.add_handler(CommandHandler("do", cmd_do))
    app.add_handler(CommandHandler("addkey", cmd_addkey))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_text))

    logger.info("Telegram Bot 已启动")
    import time as _time
    _time.sleep(0.5)  # 等待启动
    try:
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Telegram Bot 异常：{e}")


def _load_telegram_users():
    """加载 Telegram 用户角色映射"""
    try:
        import json
        if os.path.exists("data/telegram_users.json"):
            with open("data/telegram_users.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


if __name__ == "__main__":
    import time
    print("启动 Telegram Bot...")
    _run_bot()
    while True:
        time.sleep(60)

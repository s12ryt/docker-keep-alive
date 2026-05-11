from __future__ import annotations

from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .backup import BackupStore
from .state import AppState


PendingAction = dict[str, str | list[dict[str, str]]]


def _authorized(update: Update, allowed_chat_id: str) -> bool:
    return bool(update.effective_chat and str(update.effective_chat.id) == str(allowed_chat_id))


async def _reply(update: Update, text: str) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(text)


def _valid_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


def build_application(state: AppState, bot_token: str, allowed_chat_id: str) -> Application:
    app = Application.builder().token(bot_token).build()
    pending: dict[int, PendingAction] = {}

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, allowed_chat_id):
            return
        await _reply(update, "ciallo~")

    async def state_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, allowed_chat_id):
            return
        await _reply(update, state.state_text())

    async def sub_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, allowed_chat_id):
            return
        pending[update.effective_chat.id] = {"action": "sub-url"}
        await _reply(update, "我已收到請求! 請在下則訊息中給出完整網址並且不要給除了網址以外的東西:")

    async def del_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, allowed_chat_id):
            return
        urls = state.snapshot()["urls"]
        if not urls:
            await _reply(update, "目前沒有可刪除的保活網址。")
            return
        pending[update.effective_chat.id] = {"action": "del-url"}
        lines = [f"{idx}. {item['url']}" for idx, item in enumerate(urls, start=1)]
        lines.append("請打出你要刪除的網址編號:")
        await _reply(update, "\n".join(lines))

    async def notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, allowed_chat_id):
            return
        state.notify_enabled = not state.notify_enabled
        await _reply(update, f"即時通知已{'開啟' if state.notify_enabled else '關閉'}。")

    async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, allowed_chat_id):
            return
        if state.backup_url:
            await _create_backup(update, state.backup_url)
            return
        pending[update.effective_chat.id] = {"action": "backup-url"}
        await _reply(update, "我已收到請求! 請在下則訊息中給出完整的MySQL/postgres網址:")

    async def rebackup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, allowed_chat_id):
            return
        if state.backup_url:
            await _show_backups_for_restore(update, state.backup_url)
            return
        pending[update.effective_chat.id] = {"action": "rebackup-url"}
        await _reply(update, "我已收到請求! 請在下則訊息中給出完整的MySQL/postgres網址:")

    async def _create_backup(update: Update, database_url: str) -> None:
        try:
            state.backup_url = database_url
            backup_id = BackupStore(database_url).create_backup(state.snapshot())
            await _reply(update, f"備份完成，備份編號：{backup_id}")
        except Exception as exc:  # noqa: BLE001
            await _reply(update, f"備份失敗：{exc}")

    async def _show_backups_for_restore(update: Update, database_url: str) -> None:
        try:
            state.backup_url = database_url
            items = BackupStore(database_url).list_backups()
        except Exception as exc:  # noqa: BLE001
            await _reply(update, f"讀取備份失敗：{exc}")
            return
        if not items:
            await _reply(update, "目前沒有備份可恢復。")
            return
        pending[update.effective_chat.id] = {"action": "restore", "backups": [{"id": str(item["id"]), "created_at": item["created_at"]} for item in items]}
        lines = [f"{idx}. {item['created_at']} (id={item['id']})" for idx, item in enumerate(items, start=1)]
        lines.append("請打出你要恢復的備份編號:")
        await _reply(update, "\n".join(lines))

    async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, allowed_chat_id) or not update.effective_chat or not update.effective_message:
            return
        action = pending.pop(update.effective_chat.id, None)
        if not action:
            return
        text = update.effective_message.text.strip()
        kind = action.get("action")
        if kind == "sub-url":
            if not _valid_url(text):
                await _reply(update, "網址格式不正確，請使用 http:// 或 https:// 開頭。")
                return
            added = state.add_url(text)
            await _reply(update, "已新增保活網址。" if added else "這個網址已經存在。")
        elif kind == "del-url":
            if not text.isdigit():
                await _reply(update, "請輸入數字編號。")
                return
            deleted = state.delete_url(int(text) - 1)
            await _reply(update, f"已刪除：{deleted.url}" if deleted else "找不到這個編號。")
        elif kind == "backup-url":
            await _create_backup(update, text)
        elif kind == "rebackup-url":
            await _show_backups_for_restore(update, text)
        elif kind == "restore":
            backups = action.get("backups", [])
            if not text.isdigit() or int(text) < 1 or int(text) > len(backups):
                await _reply(update, "找不到這個備份編號。")
                return
            backup_id = int(backups[int(text) - 1]["id"])
            payload = BackupStore(state.backup_url).get_backup(backup_id) if state.backup_url else None
            if not payload:
                await _reply(update, "找不到這個備份。")
                return
            state.restore(payload)
            await _reply(update, "已恢復備份。")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("state", state_cmd))
    app.add_handler(CommandHandler("sub-url", sub_url))
    app.add_handler(CommandHandler("del-url", del_url))
    app.add_handler(CommandHandler("notify", notify))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("rebackup", rebackup))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    return app


async def run_bot(state: AppState, bot_token: str, allowed_chat_id: str) -> Callable[[str], Awaitable[None]]:
    application = build_application(state, bot_token, allowed_chat_id)
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    async def notify(text: str) -> None:
        await application.bot.send_message(chat_id=allowed_chat_id, text=text)

    return notify

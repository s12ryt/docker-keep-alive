from __future__ import annotations

from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .backup import BackupStore
from .state import AppState


PendingAction = dict[str, str | list[dict[str, str]]]

COMMAND_LIST_TEXT = """可用指令：
/start - 啟動 bot 並顯示這份指令列表
/help - 顯示指令列表
/commands - 顯示指令列表
/state - 查看保活網址與目前狀態
/sub-url - 新增一個保活網址
/del-url - 列出並刪除保活網址
/notify - 切換每次保活通知
/backup - 立即備份，未設定資料庫時會要求輸入 MySQL/PostgreSQL URL
/rebackup - 從備份恢復，未設定資料庫時會要求輸入 MySQL/PostgreSQL URL"""


def _authorized(update: Update, allowed_chat_id: str) -> bool:
    return bool(update.effective_chat and str(update.effective_chat.id) == str(allowed_chat_id))


async def _reply(update: Update, text: str) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(text)


def _valid_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


class BotController:
    def __init__(self, state: AppState, allowed_chat_id: str) -> None:
        self.state = state
        self.allowed_chat_id = allowed_chat_id
        self.pending: dict[int, PendingAction] = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if _authorized(update, self.allowed_chat_id):
            await _reply(update, f"ciallo~\n\n{COMMAND_LIST_TEXT}")

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if _authorized(update, self.allowed_chat_id):
            await _reply(update, COMMAND_LIST_TEXT)

    async def state_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if _authorized(update, self.allowed_chat_id):
            await _reply(update, self.state.state_text())

    async def sub_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id):
            return
        self.pending[update.effective_chat.id] = {"action": "sub-url"}
        await _reply(update, "我已收到請求! 請在下則訊息中給出完整網址並且不要給除了網址以外的東西:")

    async def del_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id):
            return
        urls = self.state.snapshot()["urls"]
        if not urls:
            await _reply(update, "目前沒有可刪除的保活網址。")
            return
        self.pending[update.effective_chat.id] = {"action": "del-url"}
        lines = [f"{idx}. {item['url']}" for idx, item in enumerate(urls, start=1)]
        lines.append("請打出你要刪除的網址編號:")
        await _reply(update, "\n".join(lines))

    async def notify(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id):
            return
        self.state.notify_enabled = not self.state.notify_enabled
        await _reply(update, f"即時通知已{'開啟' if self.state.notify_enabled else '關閉'}。")

    async def backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id):
            return
        if self.state.backup_url:
            await self._create_backup(update, self.state.backup_url)
            return
        self.pending[update.effective_chat.id] = {"action": "backup-url"}
        await _reply(update, "我已收到請求! 請在下則訊息中給出完整的MySQL/postgres網址:")

    async def rebackup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id):
            return
        if self.state.backup_url:
            await self._show_backups_for_restore(update, self.state.backup_url)
            return
        self.pending[update.effective_chat.id] = {"action": "rebackup-url"}
        await _reply(update, "我已收到請求! 請在下則訊息中給出完整的MySQL/postgres網址:")

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id) or not update.effective_chat or not update.effective_message:
            return
        action = self.pending.pop(update.effective_chat.id, None)
        if not action:
            return
        text = update.effective_message.text.strip()
        kind = action.get("action")
        if kind == "sub-url":
            await self._handle_sub_url(update, text)
        elif kind == "del-url":
            await self._handle_del_url(update, text)
        elif kind == "backup-url":
            await self._create_backup(update, text)
        elif kind == "rebackup-url":
            await self._show_backups_for_restore(update, text)
        elif kind == "restore":
            await self._handle_restore(update, text, action.get("backups", []))

    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if _authorized(update, self.allowed_chat_id):
            await _reply(update, "找不到這個指令。請輸入 /help 查看可用指令列表。")

    async def _handle_sub_url(self, update: Update, text: str) -> None:
        if not _valid_url(text):
            await _reply(update, "網址格式不正確，請使用 http:// 或 https:// 開頭。")
            return
        added = self.state.add_url(text)
        await _reply(update, "已新增保活網址。" if added else "這個網址已經存在。")

    async def _handle_del_url(self, update: Update, text: str) -> None:
        if not text.isdigit():
            await _reply(update, "請輸入數字編號。")
            return
        deleted = self.state.delete_url(int(text) - 1)
        await _reply(update, f"已刪除：{deleted.url}" if deleted else "找不到這個編號。")

    async def _create_backup(self, update: Update, database_url: str) -> None:
        try:
            self.state.backup_url = database_url
            backup_id = BackupStore(database_url).create_backup(self.state.snapshot())
            await _reply(update, f"備份完成，備份編號：{backup_id}")
        except Exception as exc:  # noqa: BLE001
            await _reply(update, f"備份失敗：{exc}")

    async def _show_backups_for_restore(self, update: Update, database_url: str) -> None:
        try:
            self.state.backup_url = database_url
            items = BackupStore(database_url).list_backups()
        except Exception as exc:  # noqa: BLE001
            await _reply(update, f"讀取備份失敗：{exc}")
            return
        if not items:
            await _reply(update, "目前沒有備份可恢復。")
            return
        self.pending[update.effective_chat.id] = {
            "action": "restore",
            "backups": [{"id": str(item["id"]), "created_at": item["created_at"]} for item in items],
        }
        lines = [f"{idx}. {item['created_at']} (id={item['id']})" for idx, item in enumerate(items, start=1)]
        lines.append("請打出你要恢復的備份編號:")
        await _reply(update, "\n".join(lines))

    async def _handle_restore(self, update: Update, text: str, backups: list[dict[str, str]]) -> None:
        if not text.isdigit() or int(text) < 1 or int(text) > len(backups):
            await _reply(update, "找不到這個備份編號。")
            return
        backup_id = int(backups[int(text) - 1]["id"])
        payload = BackupStore(self.state.backup_url).get_backup(backup_id) if self.state.backup_url else None
        if not payload:
            await _reply(update, "找不到這個備份。")
            return
        self.state.restore(payload)
        await _reply(update, "已恢復備份。")


async def sub_url_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.application.bot_data["controller"].sub_url(update, context)


async def del_url_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.application.bot_data["controller"].del_url(update, context)


def hyphen_command_handlers() -> tuple[MessageHandler, MessageHandler]:
    """Create handlers for issue-required hyphenated pseudo commands."""
    return (
        MessageHandler(filters.Regex(r"^/sub-url(?:@\w+)?(?:\s|$)"), sub_url_callback),
        MessageHandler(filters.Regex(r"^/del-url(?:@\w+)?(?:\s|$)"), del_url_callback),
    )


def build_application(state: AppState, bot_token: str, allowed_chat_id: str) -> Application:
    application = Application.builder().token(bot_token).build()
    controller = BotController(state, allowed_chat_id)
    application.bot_data["controller"] = controller
    application.add_handler(CommandHandler("start", controller.start))
    application.add_handler(CommandHandler("help", controller.help_cmd))
    application.add_handler(CommandHandler("commands", controller.help_cmd))
    application.add_handler(CommandHandler("state", controller.state_cmd))
    sub_url_handler, del_url_handler = hyphen_command_handlers()
    application.add_handler(sub_url_handler)
    application.add_handler(del_url_handler)
    application.add_handler(CommandHandler("notify", controller.notify))
    application.add_handler(CommandHandler("backup", controller.backup))
    application.add_handler(CommandHandler("rebackup", controller.rebackup))
    application.add_handler(MessageHandler(filters.COMMAND, controller.unknown_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, controller.text_message))
    return application


async def run_bot(state: AppState, bot_token: str, allowed_chat_id: str) -> Callable[[str], Awaitable[None]]:
    application = build_application(state, bot_token, allowed_chat_id)
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    async def notify(text: str) -> None:
        await application.bot.send_message(chat_id=allowed_chat_id, text=text)

    return notify

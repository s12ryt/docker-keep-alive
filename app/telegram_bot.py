from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from time import monotonic

from telegram import BotCommand, Update
from telegram.error import Conflict, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .backup import BackupStore
from .state import AppState, mask_url_for_display


PendingAction = dict[str, str | float | list[str] | list[dict[str, str]]]
logger = logging.getLogger(__name__)

COMMAND_LIST_TEXT = """可用指令：
/start - 啟動 bot 並顯示這份指令列表
/help - 顯示指令列表
/commands - 顯示指令列表
/state - 查看保活網址與目前狀態
/sub-url 或 /sub_url - 新增一個保活網址
/del-url 或 /del_url - 列出並刪除保活網址
/notify - 切換每次保活通知
/backup - 立即備份，未設定資料庫時會要求輸入 MySQL/PostgreSQL URL
/rebackup - 從備份恢復，未設定資料庫時會要求輸入 MySQL/PostgreSQL URL"""

BOT_MENU_COMMANDS = (
    ("start", "啟動 bot 並顯示指令列表"),
    ("help", "顯示指令列表"),
    ("commands", "顯示指令列表"),
    ("state", "查看保活網址與目前狀態"),
    ("sub_url", "新增一個保活網址"),
    ("del_url", "列出並刪除保活網址"),
    ("notify", "切換每次保活通知"),
    ("backup", "立即備份"),
    ("rebackup", "從備份恢復"),
)


def bot_menu_commands() -> tuple[BotCommand, ...]:
    """Build Telegram menu commands for setMyCommands.

    Telegram Bot API menu commands cannot contain hyphens, so `/sub-url` and
    `/del-url` keep working as text commands while `/sub_url` and `/del_url`
    are exposed in the native Telegram command menu.
    """
    return tuple(BotCommand(command=command, description=description) for command, description in BOT_MENU_COMMANDS)


def _authorized(update: Update, allowed_chat_id: str) -> bool:
    return bool(update.effective_chat and str(update.effective_chat.id) == str(allowed_chat_id))


async def _reply(update: Update, text: str) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(text)


def _valid_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


class BotController:
    def __init__(self, state: AppState, allowed_chat_id: str, pending_ttl_seconds: int = 300) -> None:
        self.state = state
        self.allowed_chat_id = allowed_chat_id
        self.pending_ttl_seconds = pending_ttl_seconds
        self.pending: dict[int, PendingAction] = {}

    def _clear_expired_pending(self) -> None:
        now = monotonic()
        expired_chat_ids = [
            chat_id
            for chat_id, action in self.pending.items()
            if isinstance(action.get("expires_at"), float) and now > action["expires_at"]
        ]
        for chat_id in expired_chat_ids:
            self.pending.pop(chat_id, None)

    def _set_pending(self, chat_id: int, action: PendingAction) -> None:
        self._clear_expired_pending()
        action["expires_at"] = monotonic() + self.pending_ttl_seconds
        self.pending[chat_id] = action

    def _pop_pending(self, chat_id: int) -> PendingAction | None:
        self._clear_expired_pending()
        action = self.pending.pop(chat_id, None)
        if not action:
            return None
        expires_at = action.get("expires_at")
        if isinstance(expires_at, float) and monotonic() > expires_at:
            return None
        return action

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
        self._set_pending(update.effective_chat.id, {"action": "sub-url"})
        await _reply(update, "我已收到請求! 請在下則訊息中給出完整網址並且不要給除了網址以外的東西:")

    async def del_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id):
            return
        urls = self.state.snapshot()["urls"]
        if not urls:
            await _reply(update, "目前沒有可刪除的保活網址。")
            return
        self._set_pending(update.effective_chat.id, {"action": "del-url", "urls": [item["url"] for item in urls]})
        lines = [f"{idx}. {mask_url_for_display(item['url'])}" for idx, item in enumerate(urls, start=1)]
        lines.append("請打出你要刪除的網址編號:")
        await _reply(update, "\n".join(lines))

    async def notify(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id):
            return
        enabled = self.state.toggle_notify()
        await _reply(update, f"即時通知已{'開啟' if enabled else '關閉'}。")

    async def backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id):
            return
        backup_url = self.state.get_backup_url()
        if backup_url:
            await self._create_backup(update, backup_url)
            return
        self._set_pending(update.effective_chat.id, {"action": "backup-url"})
        await _reply(update, "我已收到請求! 請在下則訊息中給出完整的MySQL/postgres網址:")

    async def rebackup(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id):
            return
        backup_url = self.state.get_backup_url()
        if backup_url:
            await self._show_backups_for_restore(update, backup_url)
            return
        self._set_pending(update.effective_chat.id, {"action": "rebackup-url"})
        await _reply(update, "我已收到請求! 請在下則訊息中給出完整的MySQL/postgres網址:")

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not _authorized(update, self.allowed_chat_id) or not update.effective_chat or not update.effective_message:
            return
        action = self._pop_pending(update.effective_chat.id)
        if not action:
            return
        text = update.effective_message.text.strip()
        kind = action.get("action")
        if kind == "sub-url":
            await self._handle_sub_url(update, text)
        elif kind == "del-url":
            await self._handle_del_url(update, text, action.get("urls", []))
        elif kind == "backup-url":
            await self._create_backup(update, text)
        elif kind == "rebackup-url":
            await self._show_backups_for_restore(update, text)
        elif kind == "restore":
            database_url = action.get("database_url")
            await self._handle_restore(update, text, action.get("backups", []), database_url if isinstance(database_url, str) else None)

    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if _authorized(update, self.allowed_chat_id):
            await _reply(update, "找不到這個指令。請輸入 /help 查看可用指令列表。")

    async def _handle_sub_url(self, update: Update, text: str) -> None:
        if not _valid_url(text):
            await _reply(update, "網址格式不正確，請使用 http:// 或 https:// 開頭。")
            return
        added = self.state.add_url(text)
        await _reply(update, "已新增保活網址。" if added else "這個網址已經存在。")

    async def _handle_del_url(self, update: Update, text: str, urls: list[str] | object = ()) -> None:
        if not text.isdigit():
            await _reply(update, "請輸入數字編號。")
            return
        candidates = urls if isinstance(urls, list) else []
        index = int(text) - 1
        if index < 0 or index >= len(candidates):
            await _reply(update, "找不到這個編號。")
            return
        deleted = self.state.delete_url_by_value(candidates[index])
        await _reply(update, f"已刪除：{mask_url_for_display(deleted.url)}" if deleted else "找不到這個網址，清單可能已變更。")

    async def _create_backup(self, update: Update, database_url: str) -> None:
        try:
            backup_id = await asyncio.to_thread(lambda: BackupStore(database_url).create_backup(self.state.backup_snapshot()))
            await _reply(update, f"備份完成，備份編號：{backup_id}")
        except Exception as exc:  # noqa: BLE001
            await _reply(update, f"備份失敗：{exc}")

    async def _show_backups_for_restore(self, update: Update, database_url: str) -> None:
        try:
            items = await asyncio.to_thread(lambda: BackupStore(database_url).list_backups())
        except Exception as exc:  # noqa: BLE001
            await _reply(update, f"讀取備份失敗：{exc}")
            return
        if not items:
            await _reply(update, "目前沒有備份可恢復。")
            return
        self._set_pending(update.effective_chat.id, {
            "action": "restore",
            "backups": [{"id": str(item["id"]), "created_at": item["created_at"]} for item in items],
            "database_url": database_url,
        })
        lines = [f"{idx}. {item['created_at']} (id={item['id']})" for idx, item in enumerate(items, start=1)]
        lines.append("請打出你要恢復的備份編號:")
        await _reply(update, "\n".join(lines))

    async def _handle_restore(self, update: Update, text: str, backups: list[dict[str, str]], database_url: str | None = None) -> None:
        if not text.isdigit() or int(text) < 1 or int(text) > len(backups):
            await _reply(update, "找不到這個備份編號。")
            return
        backup_id = int(backups[int(text) - 1]["id"])
        database_url = database_url or self.state.get_backup_url()
        if not database_url:
            await _reply(update, "沒有設定資料庫。")
            return
        payload = await asyncio.to_thread(lambda: BackupStore(database_url).get_backup(backup_id))
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
    application.add_handler(CommandHandler("sub_url", controller.sub_url))
    application.add_handler(CommandHandler("del_url", controller.del_url))
    sub_url_handler, del_url_handler = hyphen_command_handlers()
    application.add_handler(sub_url_handler)
    application.add_handler(del_url_handler)
    application.add_handler(CommandHandler("notify", controller.notify))
    application.add_handler(CommandHandler("backup", controller.backup))
    application.add_handler(CommandHandler("rebackup", controller.rebackup))
    application.add_handler(MessageHandler(filters.COMMAND, controller.unknown_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, controller.text_message))
    return application


@dataclass
class BotRuntime:
    application: Application
    conflict_retry_seconds: int = 60
    _conflict_retry_task: asyncio.Task | None = field(default=None, init=False, repr=False)

    async def notify(self, text: str, chat_id: str) -> None:
        await self.application.bot.send_message(chat_id=chat_id, text=text)

    async def stop_polling(self) -> None:
        updater = self.application.updater
        if updater and updater.running:
            try:
                await updater.stop()
            except RuntimeError:
                return

    async def start_polling(self) -> None:
        await self.application.updater.start_polling(
            drop_pending_updates=True,
            error_callback=polling_error_callback(self),
        )

    def schedule_conflict_recovery(self) -> None:
        if self._conflict_retry_task and not self._conflict_retry_task.done():
            return
        logger.warning(
            "Telegram polling conflict detected; another bot instance is already using getUpdates. "
            "Polling will retry in %s seconds while the web service keeps running.",
            self.conflict_retry_seconds,
        )
        self._conflict_retry_task = asyncio.create_task(self._recover_polling_after_conflict())

    async def _recover_polling_after_conflict(self) -> None:
        await self.stop_polling()
        await asyncio.sleep(self.conflict_retry_seconds)
        if not self.application.running:
            return
        try:
            await self.start_polling()
            logger.info("Telegram polling restarted after conflict backoff.")
        except Exception:  # noqa: BLE001 - 啟動 polling 失敗時只記錄，主服務仍需繼續
            logger.exception("Failed to restart Telegram polling after conflict backoff.")

    async def shutdown(self) -> None:
        if self._conflict_retry_task and not self._conflict_retry_task.done():
            self._conflict_retry_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._conflict_retry_task
        await self.stop_polling()
        if self.application.running:
            await self.application.stop()
        await self.application.shutdown()


def polling_error_callback(runtime: BotRuntime) -> Callable[[TelegramError], None]:
    def handle_error(error: TelegramError) -> None:
        if isinstance(error, Conflict):
            runtime.schedule_conflict_recovery()
            return
        logger.exception("Telegram polling error.", exc_info=error)

    return handle_error


async def run_bot(state: AppState, bot_token: str, allowed_chat_id: str, conflict_retry_seconds: int = 60) -> BotRuntime:
    application = build_application(state, bot_token, allowed_chat_id)
    runtime = BotRuntime(application, conflict_retry_seconds=conflict_retry_seconds)
    await application.initialize()
    await application.bot.set_my_commands(bot_menu_commands())
    await application.start()
    await runtime.start_polling()

    return runtime

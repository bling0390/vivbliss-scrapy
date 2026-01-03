from typing import Iterable, List, Tuple

from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from app.config import settings
from app.mongo import product_media


def _create_client() -> Client:
    if settings.telegram_bot_token:
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            raise RuntimeError("TG_API_ID and TG_API_HASH required with TG_BOT_TOKEN")
        return Client(
            "bot",
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
            bot_token=settings.telegram_bot_token,
            in_memory=True,
        )
    if settings.telegram_session_string:
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            raise RuntimeError("TG_API_ID and TG_API_HASH required with TG_SESSION_STRING")
        return Client(
            "user",
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
            session_string=settings.telegram_session_string,
            in_memory=True,
        )
    raise RuntimeError("Telegram credentials missing")


def _build_caption(product: dict) -> str:
    parts = [
        f"{product.get('title', 'Unknown')}",
        f"Price: {product.get('price', 'N/A')}",
        f"URL: {product.get('url')}",
    ]
    return "\n".join(parts)


def _build_keyboard(product: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("查看商品", url=product.get("url", "#"))]]
    )


def _fetch_media(product_key: str, version: int, limit: int = 10) -> List[dict]:
    cursor = product_media().find(
        {"product_key": product_key, "version": version}
    ).sort("created_at").limit(limit)
    return list(cursor)


def send_strategy_s1(product: dict, only_new: bool = False) -> Tuple[Iterable[int], str]:
    """
    S1: media_group (<=10) + caption + inline keyboard.
    If only_new is True, it will attempt to fetch only media flagged as new via payload.
    """
    target_chat = settings.telegram_target_chat
    if not target_chat:
        raise RuntimeError("TG_TARGET_CHAT not configured")

    media_docs = _fetch_media(product["product_key"], product["version"])
    if not media_docs:
        return send_strategy_s2(product)

    keyboard = _build_keyboard(product)
    caption = _build_caption(product)
    message_ids: List[int] = []

    with _create_client() as app:
        media_group = []
        for idx, media in enumerate(media_docs):
            media_group.append(
                InputMediaPhoto(
                    media.get("local_path") or media.get("source_url"),
                    caption=caption if idx == 0 else None,
                )
            )
        sent = app.send_media_group(chat_id=target_chat, media=media_group)
        message_ids.extend([m.id for m in sent])
        # send separate button message so we always include the CTA
        button_msg = app.send_message(
            chat_id=target_chat, text="查看商品", reply_markup=keyboard
        )
        message_ids.append(button_msg.id)
    return message_ids, "S1"


def send_strategy_s2(product: dict) -> Tuple[Iterable[int], str]:
    """S2: summary text + link only."""
    target_chat = settings.telegram_target_chat
    if not target_chat:
        raise RuntimeError("TG_TARGET_CHAT not configured")

    caption = _build_caption(product)
    with _create_client() as app:
        msg = app.send_message(
            chat_id=target_chat,
            text=caption,
            reply_markup=_build_keyboard(product),
        )
        return [msg.id], "S2"


def send_strategy_s3(product: dict, change: dict | None) -> Tuple[Iterable[int], str]:
    """
    S3: diff summary + newly added media.
    """
    target_chat = settings.telegram_target_chat
    if not target_chat:
        raise RuntimeError("TG_TARGET_CHAT not configured")

    changed_fields = change.get("changed_fields") if change else []
    diff_lines = [f"更新: {', '.join(changed_fields) or '内容变更'}"]
    diff_lines.append(f"{product.get('title')}")
    diff_lines.append(f"Price: {product.get('price')}")
    diff_lines.append(f"URL: {product.get('url')}")

    message_ids: List[int] = []
    with _create_client() as app:
        # send diff text first
        msg = app.send_message(
            chat_id=target_chat,
            text="\n".join(diff_lines),
            reply_markup=_build_keyboard(product),
        )
        message_ids.append(msg.id)

        # then attach only new media if we have them
        media_docs = _fetch_media(product["product_key"], product["version"])
        if media_docs:
            media_group = [
                InputMediaPhoto(doc.get("local_path") or doc.get("source_url"))
                for doc in media_docs[:10]
            ]
            sent_media = app.send_media_group(chat_id=target_chat, media=media_group)
            message_ids.extend([m.id for m in sent_media])
    return message_ids, "S3"


def send_with_strategy(strategy: str, product: dict, change: dict | None = None):
    strategy = (strategy or "S2").upper()
    if strategy == "S1":
        return send_strategy_s1(product)
    if strategy == "S3":
        return send_strategy_s3(product, change)
    return send_strategy_s2(product)

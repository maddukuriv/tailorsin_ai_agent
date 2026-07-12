from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException

from config import settings
from services.conversation_service import IncomingMessage, OutgoingMessage, handle_incoming_message


if not settings.telegram_bot_token:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

if not settings.telegram_webhook_secret:
    raise RuntimeError("TELEGRAM_WEBHOOK_SECRET is required")


router = APIRouter(prefix="/telegram", tags=["telegram"])
TELEGRAM_API_BASE_URL = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


def extract_message(update: dict[str, Any]) -> dict[str, Any] | None:
    return update.get("message") or update.get("edited_message")


def validate_webhook_secret(path_secret: str | None, header_secret: str | None) -> None:
    if path_secret is not None:
        if path_secret != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
        return

    if header_secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")


def parse_telegram_update(update: dict[str, Any]) -> IncomingMessage | None:
    message = extract_message(update)
    if not message:
        return None

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        return None

    text = (message.get("text") or "").strip()
    contact = message.get("contact") or {}

    return IncomingMessage(
        user_id=chat_id,
        text=text,
        contact_phone=contact.get("phone_number"),
        contact_user_id=contact.get("user_id"),
        source_user_id=message.get("from", {}).get("id"),
        is_start_command=text == "/start",
        metadata={"platform": "telegram", "raw_update": update},
    )


async def call_telegram_api(method: str, payload: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(f"{TELEGRAM_API_BASE_URL}/{method}", json=payload)
        response.raise_for_status()
        data = response.json()

    if not data.get("ok"):
        raise HTTPException(status_code=502, detail=f"Telegram API error: {data}")


async def send_telegram_message(chat_id: int, message: OutgoingMessage) -> None:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": message.text,
        "parse_mode": "Markdown",
    }
    if message.reply_markup is not None:
        payload["reply_markup"] = message.reply_markup
    await call_telegram_api("sendMessage", payload)


async def process_telegram_update(update: dict[str, Any]) -> dict[str, bool]:
    incoming_message = parse_telegram_update(update)
    if incoming_message is None:
        return {"ok": True}

    outgoing_messages = await handle_incoming_message(incoming_message)
    for outgoing_message in outgoing_messages:
        await send_telegram_message(incoming_message.user_id, outgoing_message)

    return {"ok": True}


@router.post("/webhook")
async def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    validate_webhook_secret(None, x_telegram_bot_api_secret_token)
    return await process_telegram_update(update)


@router.post("/webhook/{secret}")
async def telegram_webhook_with_path_secret(secret: str, update: dict[str, Any]) -> dict[str, bool]:
    validate_webhook_secret(secret, None)
    return await process_telegram_update(update)
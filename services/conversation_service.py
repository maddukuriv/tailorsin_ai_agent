from dataclasses import dataclass
from typing import Any

from conversation.intent_router import get_intent
from conversation.menu import format_menu_message_with_greeting, get_menu_keyboard
from conversation.state_manager import get_client_profile, get_session, reset_session, save_client_profile
from crm.client_type import lookup_customer_profile
from intents.browse import build_browse_response


@dataclass
class IncomingMessage:
    user_id: int
    text: str = ""
    contact_phone: str | None = None
    contact_user_id: int | None = None
    source_user_id: int | None = None
    is_start_command: bool = False
    metadata: dict[str, Any] | None = None


@dataclass
class OutgoingMessage:
    text: str
    reply_markup: dict[str, Any] | None = None


def build_intent_response(intent_name: str, client_type: str) -> list[OutgoingMessage] | None:
    if intent_name == "browse":
        return [
            OutgoingMessage(
                text=build_browse_response(),
                reply_markup=build_menu_reply_markup(client_type),
            )
        ]

    return None


RETURNING_CLIENT_TYPES = {"active_client", "client"}


def normalize_mobile(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def extract_mobile_from_text(text: str) -> str | None:
    normalized = normalize_mobile(text)
    if 10 <= len(normalized) <= 15:
        return normalized
    return None


def resolve_mobile(
    text: str,
    contact_phone: str | None,
    fallback_mobile: str | None = None,
) -> str | None:
    if contact_phone:
        mobile_from_contact = normalize_mobile(contact_phone)
        if mobile_from_contact:
            return mobile_from_contact

    mobile_from_text = extract_mobile_from_text(text) if text else None
    if mobile_from_text:
        return mobile_from_text

    return fallback_mobile


def resolve_client_type(
    text: str,
    contact_phone: str | None,
    fallback_mobile: str | None = None,
) -> tuple[str | None, str, str | None]:
    mobile = resolve_mobile(text, contact_phone, fallback_mobile)
    customer_profile = lookup_customer_profile(mobile or "")
    return mobile, customer_profile.client_type, customer_profile.customer_salutation


def build_contact_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [[{"text": "Share mobile number", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def build_menu_reply_markup(client_type: str) -> dict[str, Any]:
    return {
        "keyboard": get_menu_keyboard(client_type),
        "resize_keyboard": True,
    }


def send_main_menu(
    client_type: str,
    customer_salutation: str | None = None,
    is_repeat: bool = False,
) -> OutgoingMessage:
    return OutgoingMessage(
        text=format_menu_message_with_greeting(client_type, customer_salutation, is_repeat),
        reply_markup=build_menu_reply_markup(client_type),
    )


def build_main_menu_response(
    user_id: int,
    client_type: str,
    customer_salutation: str | None,
) -> OutgoingMessage:
    session = get_session(user_id)
    is_repeat = client_type in RETURNING_CLIENT_TYPES and session.has_seen_known_customer_menu

    if client_type in RETURNING_CLIENT_TYPES:
        session.has_seen_known_customer_menu = True

    return send_main_menu(client_type, customer_salutation, is_repeat)


def handle_incoming_message(message: IncomingMessage) -> list[OutgoingMessage]:
    existing_session = get_session(message.user_id)
    existing_mobile, existing_client_type, existing_customer_salutation = get_client_profile(message.user_id)

    if message.is_start_command:
        has_seen_known_customer_menu = existing_session.has_seen_known_customer_menu
        reset_session(message.user_id)
        reset_session(message.user_id).has_seen_known_customer_menu = has_seen_known_customer_menu
        mobile, client_type, customer_salutation = resolve_client_type(
            message.text,
            message.contact_phone,
            existing_mobile,
        )
        save_client_profile(message.user_id, mobile, client_type, customer_salutation)
        return [build_main_menu_response(message.user_id, client_type, customer_salutation)]

    mobile_from_text = extract_mobile_from_text(message.text) if message.text else None
    if mobile_from_text:
        mobile, client_type, customer_salutation = resolve_client_type(message.text, message.contact_phone, existing_mobile)
        save_client_profile(message.user_id, mobile, client_type, customer_salutation)
        return [build_main_menu_response(message.user_id, client_type, customer_salutation)]

    if message.contact_phone:
        if message.contact_user_id not in (None, message.source_user_id):
            return [OutgoingMessage(text="Please share your own mobile number using the button.")]

        mobile = normalize_mobile(message.contact_phone)
        if not mobile:
            return [OutgoingMessage(text="I could not read that mobile number. Please try again.")]

        mobile, client_type, customer_salutation = resolve_client_type(message.text, message.contact_phone, existing_mobile)
        save_client_profile(message.user_id, mobile, client_type, customer_salutation)
        return [build_main_menu_response(message.user_id, client_type, customer_salutation)]

    mobile, client_type, customer_salutation = existing_mobile, existing_client_type, existing_customer_salutation
    if not mobile or not client_type:
        mobile, client_type, customer_salutation = resolve_client_type(message.text, message.contact_phone, existing_mobile)
        save_client_profile(message.user_id, mobile, client_type, customer_salutation)

    if message.text in {"menu", "main menu", "10", "0"}:
        if mobile:
            _, client_type, customer_salutation = resolve_client_type(message.text, message.contact_phone, mobile)
            save_client_profile(message.user_id, mobile, client_type, customer_salutation)
        return [build_main_menu_response(message.user_id, client_type, customer_salutation)]

    if message.text:
        selected_intent = get_intent(client_type, message.text)
        if selected_intent is None:
            return [
                OutgoingMessage(text="Please choose one of the listed menu options."),
                build_main_menu_response(message.user_id, client_type, customer_salutation),
            ]

        intent_response = build_intent_response(selected_intent, client_type)
        if intent_response is not None:
            return intent_response

        return [OutgoingMessage(text=f"Selected option: {selected_intent}")]

    return []
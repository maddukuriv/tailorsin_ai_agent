from dataclasses import dataclass
from datetime import date, timedelta
import logging
import time
from typing import Any

from conversation.intent_router import get_intent
from conversation.menu import format_menu_message_with_greeting, get_menu_keyboard
from conversation.state_manager import (
    get_client_profile,
    get_session,
    mark_awaiting_contact,
    reset_session,
    save_client_profile,
)
from crm.alteration_pickup import schedule_alteration_pickup
from crm.book_appointment import book_store_visit, fetch_available_visit_slots
from crm.client_address import add_client_address, fetch_client_addresses, update_client_address
from crm.client_type import lookup_customer_profile
from crm.cancel_order import cancel_current_order
from crm.fabric_delivery import create_fabric_delivery_request
from crm.fabric_alert import raise_fabric_alert
from crm.human_handover import request_human_handover
from crm.order_change_request import create_order_change_request, list_order_change_requests
from crm.order_status import fetch_current_order_status
from crm.schedule_pickup import schedule_fresh_pickup
from crm.user_register import register_new_client
from intents.browse import build_browse_response
from intents.measurements import build_measurements_response
from intents.order_status import build_order_status_response
from intents.pricing import build_pricing_response
from intents.visit_history import build_visit_history_response


logger = logging.getLogger(__name__)


TAILORSIN_OVERVIEW = (
    "How the process works:\n\n"
    "1. Schedule a pickup.\n"
    "2. Hand over your fabric along with a sample or reference garment.\n"
    "3. Within 6 business hours, our team will contact you to confirm design details and share a detailed estimate.\n"
    "4. Once you approve the estimate and complete the payment, we confirm the delivery timeline and begin production.\n"
    "5. If you choose not to proceed, your unstitched fabric will be safely returned.\n"
    "6. After production, an e-invoice will be generated.\n"
    "7. Your stitched outfits will be delivered to your doorstep.\n"
    "8. Free alterations are available within 7 days of delivery.\n\n"
    "Our goal is to make tailoring hassle-free and convenient."
)

MEASUREMENT_POLICY = (
    "Currently, we do not offer home measurement services due to quality control and customer privacy reasons. "
    "To ensure a reliable fit, please share a sample or reference outfit during pickup, or book a store visit by appointment."
)

DELIVERY_TIMELINE = (
    "Most orders are completed within 24 hours of cloth pickup once the design and estimate are approved. "
    "For complex garments, detailed embroidery, or special finishing, our team confirms the committed delivery date during order approval."
)

SERVICE_AREAS = (
    "We currently serve Hyderabad, but we accept orders from other locations as well. "
    "Share your area or pincode and we will confirm pickup and delivery availability for your location before scheduling."
)


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
    if intent_name == "about":
        return [
            OutgoingMessage(
                text=TAILORSIN_OVERVIEW,
                reply_markup=build_menu_reply_markup(client_type),
            )
        ]

    if intent_name == "browse":
        return [
            OutgoingMessage(
                text=build_browse_response(),
                reply_markup=build_menu_reply_markup(client_type),
            )
        ]

    if intent_name == "measurement":
        return [
            OutgoingMessage(
                text=MEASUREMENT_POLICY,
                reply_markup=build_menu_reply_markup(client_type),
            )
        ]

    if intent_name == "delivery":
        return [
            OutgoingMessage(
                text=DELIVERY_TIMELINE,
                reply_markup=build_menu_reply_markup(client_type),
            )
        ]

    if intent_name == "service_area":
        return [
            OutgoingMessage(
                text=SERVICE_AREAS,
                reply_markup=build_menu_reply_markup(client_type),
            )
        ]

    if intent_name == "pricing":
        return [
            OutgoingMessage(
                text=build_pricing_response(client_type),
                reply_markup=build_menu_reply_markup(client_type),
            )
        ]

    return None


RETURNING_CLIENT_TYPES = {"active_client", "client"}
SESSION_TIMEOUT_SECONDS = 120


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


def derive_mobile_from_message(message: IncomingMessage, fallback_mobile: str | None = None) -> str | None:
    if fallback_mobile:
        return fallback_mobile

    metadata = message.metadata or {}
    platform = str(metadata.get("platform", "")).strip().lower()
    if platform == "wati":
        candidate = normalize_mobile(str(message.user_id))
        if 10 <= len(candidate) <= 15:
            return candidate

    return None


def is_telegram_message(message: IncomingMessage) -> bool:
    metadata = message.metadata or {}
    return str(metadata.get("platform", "")).strip().lower() == "telegram"


def is_onboarding_trigger(message: IncomingMessage) -> bool:
    if message.is_start_command:
        return True

    normalized_text = (message.text or "").strip().casefold()
    return normalized_text in {"hi", "hello", "menu", "main menu", "start"}


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


def build_pickup_time_reply_markup() -> dict[str, Any]:
    return {
        "keyboard": [
            [{"text": "1. Morning (9 AM - 2 PM)"}],
            [{"text": "2. Afternoon (2 PM - 9 PM)"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def parse_pickup_time_option(raw_text: str) -> int | None:
    normalized_text = (raw_text or "").strip().casefold()
    if normalized_text in {
        "1",
        "1. 9am-2pm",
        "1. morning (9 am - 2 pm)",
        "morning",
    }:
        return 1
    if normalized_text in {
        "2",
        "2. 2pm-9pm",
        "2. afternoon (2 pm - 9 pm)",
        "afternoon",
    }:
        return 2
    return None


def get_pickup_date_choices() -> list[tuple[str, str]]:
    today = date.today()
    return [
        ("1", today.isoformat()),
        ("2", (today + timedelta(days=1)).isoformat()),
        ("3", (today + timedelta(days=2)).isoformat()),
    ]


def build_pickup_date_reply_markup() -> dict[str, Any]:
    choices = get_pickup_date_choices()
    return {
        "keyboard": [[{"text": f"{index}. {value}"}] for index, value in choices],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def parse_pickup_date_option(raw_text: str) -> str | None:
    normalized_text = (raw_text or "").strip()
    choice_lookup = {index: value for index, value in get_pickup_date_choices()}

    if normalized_text in choice_lookup:
        return choice_lookup[normalized_text]

    for index, value in get_pickup_date_choices():
        if normalized_text == f"{index}. {value}":
            return value

    # Keep ISO-date input accepted as a fallback.
    try:
        pickup_date = date.fromisoformat(normalized_text)
    except ValueError:
        return None

    if pickup_date < date.today():
        return None

    return pickup_date.isoformat()


def build_visit_slot_reply_markup(slots: list[str]) -> dict[str, Any]:
    return {
        "keyboard": [[{"text": f"{index + 1}. {slot}"}] for index, slot in enumerate(slots)],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def parse_visit_slot_option(raw_text: str, slots: list[str]) -> str | None:
    normalized_text = (raw_text or "").strip()
    if not normalized_text or not slots:
        return None

    if normalized_text.isdigit():
        index = int(normalized_text) - 1
        if 0 <= index < len(slots):
            return slots[index]

    for index, slot in enumerate(slots, start=1):
        if normalized_text == f"{index}. {slot}":
            return slot
        if normalized_text.casefold() == slot.casefold():
            return slot

    return None


def clear_address_update_flow(session: Any) -> None:
    session.awaiting_address_action = False
    session.awaiting_address_add_line = False
    session.awaiting_address_add_city = False
    session.awaiting_address_add_pincode = False
    session.awaiting_address_update_id = False
    session.awaiting_address_update_line = False
    session.awaiting_address_set_main = False
    session.pending_address_line = None
    session.pending_address_city = None
    session.pending_address_id = None


def clear_pickup_flow(session: Any) -> None:
    session.awaiting_pickup_date = False
    session.awaiting_pickup_time = False
    session.awaiting_alteration_pickup_notes = False
    session.pending_pickup_date = None
    session.pending_pickup_time = None
    session.pickup_mode = None


def clear_order_change_flow(session: Any) -> None:
    session.awaiting_order_change_type = False
    session.awaiting_order_change_details = False
    session.pending_order_change_type = None


def clear_order_cancel_flow(session: Any) -> None:
    session.awaiting_order_cancel_reason = False


def build_address_list_message(mobile: str) -> str:
    result = fetch_client_addresses(mobile)
    if not result.success:
        return result.message

    lines: list[str] = []
    if result.customer_name:
        lines.append(f"Saved addresses for {result.customer_name}:")
    else:
        lines.append("Saved addresses:")
    lines.append("")

    if result.addresses:
        for address in result.addresses:
            main_tag = " (Main)" if address.is_main else ""
            location_parts = [part for part in [address.address1, address.city, address.pincode] if part]
            lines.append(f"ID {address.address_id}: {', '.join(location_parts)}{main_tag}")
    else:
        lines.append("No saved addresses found.")

    lines.extend(
        [
            "",
            "Reply 1 to add a new address.",
            "Reply 2 to update an address or set one as main.",
        ]
    )
    return "\n".join(lines)


ORDER_CHANGE_TYPE_MAP = {
    "1": "design_change",
    "2": "size_change",
    "3": "item_change",
    "4": "cancel",
    "5": "other",
}


def build_order_change_intro_message(mobile: str) -> str:
    result = list_order_change_requests(mobile)
    lines: list[str] = []

    if result.success and result.requests:
        lines.append("Recent change requests:")
        for request in result.requests[:3]:
            request_id = request.request_id if request.request_id is not None else "-"
            order_id = request.order_id if request.order_id is not None else "-"
            lines.append(
                f"- Req {request_id} | Order {order_id} | {request.request_type} | {request.status_label}"
            )
        lines.append("")
    elif result.success:
        lines.append("No previous change requests found.")
        lines.append("")
    else:
        lines.append(result.message)
        lines.append("")

    lines.extend(
        [
            "Choose request type:",
            "1. Design change",
            "2. Size change",
            "3. Item change",
            "4. Cancel",
            "5. Other",
        ]
    )
    return "\n".join(lines)


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
    now = time.time()
    existing_session = get_session(message.user_id)

    if now - existing_session.last_activity_at > SESSION_TIMEOUT_SECONDS:
        reset_session(message.user_id)
        existing_session = get_session(message.user_id)

    existing_session.last_activity_at = now
    existing_mobile, existing_client_type, existing_customer_salutation = get_client_profile(message.user_id)
    auto_mobile = derive_mobile_from_message(message, existing_mobile)

    logger.info(
        "incoming_message user_id=%s text=%r start=%s mobile_known=%s auto_mobile=%s client_type=%s",
        message.user_id,
        (message.text or "")[:80],
        message.is_start_command,
        bool(existing_mobile),
        bool(auto_mobile),
        existing_client_type,
    )

    if is_telegram_message(message) and not existing_mobile and not message.contact_phone:
        if existing_session.awaiting_contact or is_onboarding_trigger(message):
            mark_awaiting_contact(message.user_id)
            logger.info("onboarding_request_contact user_id=%s", message.user_id)
            return [
                OutgoingMessage(
                    text="Please share your mobile number using the button below.",
                    reply_markup=build_contact_keyboard(),
                )
            ]

    if message.is_start_command:
        has_seen_known_customer_menu = existing_session.has_seen_known_customer_menu
        reset_session(message.user_id)
        reset_session(message.user_id).has_seen_known_customer_menu = has_seen_known_customer_menu
        mobile, client_type, customer_salutation = resolve_client_type(
            message.text,
            message.contact_phone,
            auto_mobile,
        )
        save_client_profile(message.user_id, mobile, client_type, customer_salutation)
        logger.info(
            "start_flow user_id=%s resolved_client_type=%s mobile_present=%s",
            message.user_id,
            client_type,
            bool(mobile),
        )
        return [build_main_menu_response(message.user_id, client_type, customer_salutation)]

    if existing_session.awaiting_registration_name:
        registration_name = (message.text or "").strip()
        if len(registration_name) < 2:
            return [OutgoingMessage(text="Please enter a valid full name for registration.")]

        mobile_for_registration = derive_mobile_from_message(message, existing_mobile)
        if not mobile_for_registration:
            existing_session.awaiting_registration_name = False
            return [
                OutgoingMessage(
                    text="I could not detect your mobile number automatically for this session, so registration could not be completed.",
                )
            ]

        registration_result = register_new_client(mobile_for_registration, registration_name)
        existing_session.awaiting_registration_name = False

        logger.info(
            "registration_attempt user_id=%s mobile_present=%s success=%s",
            message.user_id,
            bool(mobile_for_registration),
            registration_result.success,
        )

        if registration_result.success:
            mobile, client_type, customer_salutation = resolve_client_type(
                message.text,
                message.contact_phone,
                mobile_for_registration,
            )
            save_client_profile(message.user_id, mobile, client_type, customer_salutation)
            return [
                OutgoingMessage(text=registration_result.message),
                build_main_menu_response(message.user_id, client_type, customer_salutation),
            ]

        return [
            OutgoingMessage(
                text=registration_result.message,
                reply_markup=build_menu_reply_markup(existing_client_type or "new_user"),
            )
        ]

    if existing_session.awaiting_pickup_date:
        pickup_date = parse_pickup_date_option(message.text)
        if pickup_date is None:
            return [
                OutgoingMessage(
                    text=(
                        "Please choose a valid pickup date option:\n"
                        "1. Today's date\n"
                        "2. Tomorrow's date\n"
                        "3. Day after tomorrow"
                    ),
                    reply_markup=build_pickup_date_reply_markup(),
                )
            ]

        existing_session.pending_pickup_date = pickup_date
        existing_session.awaiting_pickup_date = False
        existing_session.awaiting_pickup_time = True
        return [
            OutgoingMessage(
                text="Choose pickup time slot:\n1. Morning (9 AM - 2 PM)\n2. Afternoon (2 PM - 9 PM)",
                reply_markup=build_pickup_time_reply_markup(),
            )
        ]

    if existing_session.awaiting_pickup_time:
        pickup_time = parse_pickup_time_option(message.text)
        if pickup_time is None:
            return [
                OutgoingMessage(
                    text="Please choose a valid pickup slot: 1 for Morning or 2 for Afternoon.",
                    reply_markup=build_pickup_time_reply_markup(),
                )
            ]

        mobile_for_pickup = derive_mobile_from_message(message, existing_mobile)
        pickup_date = existing_session.pending_pickup_date
        pickup_mode = existing_session.pickup_mode or "fresh"

        if not mobile_for_pickup or not pickup_date:
            clear_pickup_flow(existing_session)
            return [
                OutgoingMessage(
                    text="Unable to schedule pickup because mobile or pickup date is missing. Please choose option 1 again.",
                    reply_markup=build_menu_reply_markup(existing_client_type or "client"),
                )
            ]

        if pickup_mode == "alteration":
            existing_session.awaiting_pickup_time = False
            existing_session.awaiting_alteration_pickup_notes = True
            existing_session.pending_pickup_time = pickup_time
            return [
                OutgoingMessage(
                    text=(
                        "Please share alteration/request notes (optional).\n"
                        "Example: Shirt sleeves need to be shortened.\n"
                        "Reply with 'skip' to continue without notes."
                    )
                )
            ]

        schedule_result = schedule_fresh_pickup(mobile_for_pickup, pickup_date, pickup_time)
        clear_pickup_flow(existing_session)
        if schedule_result.success:
            return [
                OutgoingMessage(text=schedule_result.message),
                build_main_menu_response(message.user_id, existing_client_type or "client", existing_customer_salutation),
            ]

        if schedule_result.conflict_open_order:
            return [
                OutgoingMessage(
                    text=(
                        f"{schedule_result.message}\n"
                        "You already have an active open order. Please use pickup alteration flow instead."
                    ),
                    reply_markup=build_menu_reply_markup(existing_client_type or "client"),
                )
            ]

        return [
            OutgoingMessage(
                text=schedule_result.message,
                reply_markup=build_menu_reply_markup(existing_client_type or "client"),
            )
        ]

    if existing_session.awaiting_alteration_pickup_notes:
        mobile_for_pickup = derive_mobile_from_message(message, existing_mobile)
        pickup_date = existing_session.pending_pickup_date
        pickup_time = existing_session.pending_pickup_time
        notes = (message.text or "").strip()
        if notes.casefold() in {"skip", "no", "none"}:
            notes = ""

        clear_pickup_flow(existing_session)

        if not mobile_for_pickup or not pickup_date or pickup_time is None:
            return [
                OutgoingMessage(
                    text="Unable to schedule alteration pickup due to missing details. Please choose option 2 again.",
                    reply_markup=build_menu_reply_markup(existing_client_type or "active_client"),
                )
            ]

        alteration_result = schedule_alteration_pickup(
            mobile=mobile_for_pickup,
            pickup_date=pickup_date,
            pickup_time=pickup_time,
            notes=notes,
        )
        return [
            OutgoingMessage(
                text=alteration_result.message,
                reply_markup=build_menu_reply_markup(existing_client_type or "active_client"),
            )
        ]

    if existing_session.awaiting_visit_date:
        visit_date = parse_pickup_date_option(message.text)
        if visit_date is None:
            return [
                OutgoingMessage(
                    text=(
                        "Please choose a valid visit date option:\n"
                        "1. Today's date\n"
                        "2. Tomorrow's date\n"
                        "3. Day after tomorrow"
                    ),
                    reply_markup=build_pickup_date_reply_markup(),
                )
            ]

        availability_result = fetch_available_visit_slots(visit_date)
        if not availability_result.success:
            return [
                OutgoingMessage(
                    text=availability_result.message,
                    reply_markup=build_pickup_date_reply_markup(),
                )
            ]

        existing_session.pending_visit_date = visit_date
        existing_session.pending_visit_slots = availability_result.slots
        existing_session.awaiting_visit_date = False
        existing_session.awaiting_visit_time = True

        slot_lines = [
            "Choose available visit slot:",
            *[f"{index + 1}. {slot}" for index, slot in enumerate(availability_result.slots)],
        ]
        return [
            OutgoingMessage(
                text="\n".join(slot_lines),
                reply_markup=build_visit_slot_reply_markup(availability_result.slots),
            )
        ]

    if existing_session.awaiting_visit_time:
        selected_slot = parse_visit_slot_option(message.text, existing_session.pending_visit_slots)
        if selected_slot is None:
            return [
                OutgoingMessage(
                    text="Please choose a valid slot from the listed options.",
                    reply_markup=build_visit_slot_reply_markup(existing_session.pending_visit_slots),
                )
            ]

        visit_mobile = derive_mobile_from_message(message, existing_mobile)
        visit_date = existing_session.pending_visit_date

        existing_session.awaiting_visit_time = False
        existing_session.pending_visit_date = None
        existing_session.pending_visit_slots = []

        if not visit_mobile or not visit_date:
            return [
                OutgoingMessage(
                    text="Unable to schedule store visit because mobile or date is missing. Please choose option 3 again.",
                    reply_markup=build_menu_reply_markup(existing_client_type or "client"),
                )
            ]

        book_result = book_store_visit(visit_mobile, visit_date, selected_slot)
        if book_result.success:
            return [
                OutgoingMessage(text=book_result.message),
                build_main_menu_response(message.user_id, existing_client_type or "client", existing_customer_salutation),
            ]

        return [
            OutgoingMessage(
                text=book_result.message,
                reply_markup=build_menu_reply_markup(existing_client_type or "client"),
            )
        ]

    if existing_session.awaiting_fabric_delivery_notes:
        mobile_for_fabric_delivery = derive_mobile_from_message(message, existing_mobile)
        existing_session.awaiting_fabric_delivery_notes = False

        if not mobile_for_fabric_delivery:
            return [
                OutgoingMessage(
                    text="I could not identify your mobile number for fabric delivery request. Please share contact or send your mobile number.",
                    reply_markup=build_menu_reply_markup(existing_client_type or "client"),
                )
            ]

        notes = (message.text or "").strip()
        if notes.casefold() in {"skip", "no", "none"}:
            notes = ""

        fabric_delivery_result = create_fabric_delivery_request(mobile_for_fabric_delivery, notes=notes)
        return [
            OutgoingMessage(
                text=fabric_delivery_result.message,
                reply_markup=build_menu_reply_markup(existing_client_type or "client"),
            )
        ]

    if existing_session.awaiting_address_action:
        normalized_text = (message.text or "").strip().casefold()
        if normalized_text in {"1", "add", "add address"}:
            existing_session.awaiting_address_action = False
            existing_session.awaiting_address_add_line = True
            return [OutgoingMessage(text="Please enter address line (house/area/street).")]

        if normalized_text in {"2", "update", "update address", "set main"}:
            existing_session.awaiting_address_action = False
            existing_session.awaiting_address_update_id = True
            return [OutgoingMessage(text="Please enter the Address ID you want to update/set as main.")]

        return [
            OutgoingMessage(
                text="Please reply 1 to add new address or 2 to update/set main.",
            )
        ]

    if existing_session.awaiting_address_add_line:
        address_line = (message.text or "").strip()
        if len(address_line) < 5:
            return [OutgoingMessage(text="Please enter a valid address line.")]

        existing_session.pending_address_line = address_line
        existing_session.awaiting_address_add_line = False
        existing_session.awaiting_address_add_city = True
        return [OutgoingMessage(text="Please enter city name.")]

    if existing_session.awaiting_address_add_city:
        city = (message.text or "").strip()
        if len(city) < 2:
            return [OutgoingMessage(text="Please enter a valid city name.")]

        existing_session.pending_address_city = city
        existing_session.awaiting_address_add_city = False
        existing_session.awaiting_address_add_pincode = True
        return [OutgoingMessage(text="Please enter 6-digit pincode.")]

    if existing_session.awaiting_address_add_pincode:
        pincode = normalize_mobile(message.text or "")
        if len(pincode) != 6:
            return [OutgoingMessage(text="Please enter a valid 6-digit pincode.")]

        mobile_for_address = derive_mobile_from_message(message, existing_mobile)
        address_line = existing_session.pending_address_line
        city = existing_session.pending_address_city
        clear_address_update_flow(existing_session)

        if not mobile_for_address or not address_line or not city:
            return [
                OutgoingMessage(
                    text="Unable to add address due to missing details. Please choose option 8 again.",
                    reply_markup=build_menu_reply_markup(existing_client_type or "client"),
                )
            ]

        add_result = add_client_address(mobile_for_address, address_line, city, pincode)
        return [
            OutgoingMessage(
                text=add_result.message,
                reply_markup=build_menu_reply_markup(existing_client_type or "client"),
            )
        ]

    if existing_session.awaiting_address_update_id:
        address_id_text = normalize_mobile(message.text or "")
        if not address_id_text:
            return [OutgoingMessage(text="Please enter a valid numeric Address ID.")]

        existing_session.pending_address_id = int(address_id_text)
        existing_session.awaiting_address_update_id = False
        existing_session.awaiting_address_update_line = True
        return [
            OutgoingMessage(
                text="Enter new address line to update, or reply 'skip' to keep existing line.",
            )
        ]

    if existing_session.awaiting_address_update_line:
        update_line = (message.text or "").strip()
        if update_line.casefold() in {"skip", "no", "none"}:
            existing_session.pending_address_line = None
        else:
            if len(update_line) < 5:
                return [OutgoingMessage(text="Please enter a valid address line or reply 'skip'.")]
            existing_session.pending_address_line = update_line

        existing_session.awaiting_address_update_line = False
        existing_session.awaiting_address_set_main = True
        return [OutgoingMessage(text="Set this address as main? Reply yes or no.")]

    if existing_session.awaiting_address_set_main:
        normalized_text = (message.text or "").strip().casefold()
        if normalized_text in {"yes", "y", "1", "set main", "main"}:
            set_main = True
        elif normalized_text in {"no", "n", "0", "skip"}:
            set_main = None
        else:
            return [OutgoingMessage(text="Please reply yes or no.")]

        mobile_for_address = derive_mobile_from_message(message, existing_mobile)
        address_id = existing_session.pending_address_id
        address_line = existing_session.pending_address_line
        clear_address_update_flow(existing_session)

        if not mobile_for_address or address_id is None:
            return [
                OutgoingMessage(
                    text="Unable to update address due to missing details. Please choose option 8 again.",
                    reply_markup=build_menu_reply_markup(existing_client_type or "client"),
                )
            ]

        update_result = update_client_address(
            mobile_for_address,
            address_id=address_id,
            address1=address_line,
            set_main=set_main,
        )
        return [
            OutgoingMessage(
                text=update_result.message,
                reply_markup=build_menu_reply_markup(existing_client_type or "client"),
            )
        ]

    if existing_session.awaiting_order_change_type:
        normalized_text = (message.text or "").strip().casefold()
        selected_type = ORDER_CHANGE_TYPE_MAP.get(normalized_text)
        if selected_type is None:
            return [
                OutgoingMessage(
                    text=(
                        "Please choose a valid request type:\n"
                        "1. Design change\n"
                        "2. Size change\n"
                        "3. Item change\n"
                        "4. Cancel\n"
                        "5. Other"
                    )
                )
            ]

        existing_session.pending_order_change_type = selected_type
        existing_session.awaiting_order_change_type = False
        existing_session.awaiting_order_change_details = True
        return [OutgoingMessage(text="Please describe your requested changes in detail.")]

    if existing_session.awaiting_order_change_details:
        details = (message.text or "").strip()
        if len(details) < 5:
            return [OutgoingMessage(text="Please enter a valid request description.")]

        mobile_for_change = derive_mobile_from_message(message, existing_mobile)
        request_type = existing_session.pending_order_change_type or "other"
        clear_order_change_flow(existing_session)

        if not mobile_for_change:
            return [
                OutgoingMessage(
                    text="I could not identify your mobile number for order change request. Please share contact or send your mobile number.",
                    reply_markup=build_menu_reply_markup(existing_client_type or "active_client"),
                )
            ]

        create_result = create_order_change_request(
            mobile=mobile_for_change,
            request_type=request_type,
            details=details,
        )
        return [
            OutgoingMessage(
                text=create_result.message,
                reply_markup=build_menu_reply_markup(existing_client_type or "active_client"),
            )
        ]

    if existing_session.awaiting_order_cancel_reason:
        reason = (message.text or "").strip()
        if len(reason) < 3:
            return [OutgoingMessage(text="Please enter a valid cancellation reason.")]

        mobile_for_cancel = derive_mobile_from_message(message, existing_mobile)
        clear_order_cancel_flow(existing_session)

        if not mobile_for_cancel:
            return [
                OutgoingMessage(
                    text="I could not identify your mobile number for order cancellation. Please share contact or send your mobile number.",
                    reply_markup=build_menu_reply_markup(existing_client_type or "active_client"),
                )
            ]

        status_result = fetch_current_order_status(mobile_for_cancel)
        order_id = status_result.order.order_id if status_result.success and status_result.order else None
        order_id_int = int(order_id) if isinstance(order_id, str) and order_id.isdigit() else None

        cancel_result = cancel_current_order(
            mobile=mobile_for_cancel,
            order_id=order_id_int,
            reason=reason,
        )
        return [
            OutgoingMessage(
                text=cancel_result.message,
                reply_markup=build_menu_reply_markup(existing_client_type or "active_client"),
            )
        ]

    mobile_from_text = extract_mobile_from_text(message.text) if message.text else None
    if mobile_from_text:
        mobile, client_type, customer_salutation = resolve_client_type(message.text, message.contact_phone, auto_mobile)
        save_client_profile(message.user_id, mobile, client_type, customer_salutation)
        return [build_main_menu_response(message.user_id, client_type, customer_salutation)]

    if message.contact_phone:
        if message.contact_user_id not in (None, message.source_user_id):
            return [OutgoingMessage(text="Please share your own mobile number using the button.")]

        mobile = normalize_mobile(message.contact_phone)
        if not mobile:
            return [OutgoingMessage(text="I could not read that mobile number. Please try again.")]

        mobile, client_type, customer_salutation = resolve_client_type(message.text, message.contact_phone, auto_mobile)
        save_client_profile(message.user_id, mobile, client_type, customer_salutation)
        logger.info(
            "onboarding_contact_captured user_id=%s mobile_present=%s client_type=%s",
            message.user_id,
            bool(mobile),
            client_type,
        )
        return [build_main_menu_response(message.user_id, client_type, customer_salutation)]

    mobile, client_type, customer_salutation = existing_mobile, existing_client_type, existing_customer_salutation
    if not mobile or not client_type:
        mobile, client_type, customer_salutation = resolve_client_type(message.text, message.contact_phone, auto_mobile)
        save_client_profile(message.user_id, mobile, client_type, customer_salutation)

    if message.text in {"menu", "main menu", "10", "0"}:
        if mobile:
            _, client_type, customer_salutation = resolve_client_type(message.text, message.contact_phone, mobile)
            save_client_profile(message.user_id, mobile, client_type, customer_salutation)
        return [build_main_menu_response(message.user_id, client_type, customer_salutation)]

    if message.text:
        selected_intent = get_intent(client_type, message.text)
        logger.info(
            "intent_resolved user_id=%s client_type=%s intent=%s text=%r",
            message.user_id,
            client_type,
            selected_intent,
            (message.text or "")[:80],
        )
        if selected_intent is None:
            return [
                OutgoingMessage(text="Please choose one of the listed menu options."),
                build_main_menu_response(message.user_id, client_type, customer_salutation),
            ]

        if selected_intent == "register":
            mobile_for_registration = derive_mobile_from_message(message, mobile)
            if mobile_for_registration:
                save_client_profile(message.user_id, mobile_for_registration, client_type, customer_salutation)

            existing_session.awaiting_registration_name = True
            return [OutgoingMessage(text="Please enter your full name for registration.")]

        if selected_intent == "new_order":
            clear_pickup_flow(existing_session)
            existing_session.awaiting_pickup_date = True
            existing_session.pickup_mode = "alteration" if client_type == "active_client" else "fresh"

            pickup_intro = "Please choose pickup date:"
            if existing_session.pickup_mode == "alteration":
                pickup_intro = "Please choose alteration/another pickup date:"

            return [
                OutgoingMessage(
                    text=(
                        f"{pickup_intro}\n"
                        "1. Today's date\n"
                        "2. Tomorrow's date\n"
                        "3. Day after tomorrow"
                    ),
                    reply_markup=build_pickup_date_reply_markup(),
                )
            ]

        if selected_intent in {"book_visit", "visit"}:
            existing_session.awaiting_visit_date = True
            existing_session.awaiting_visit_time = False
            existing_session.pending_visit_date = None
            existing_session.pending_visit_slots = []
            return [
                OutgoingMessage(
                    text=(
                        "Please choose visit date:\n"
                        "1. Today's date\n"
                        "2. Tomorrow's date\n"
                        "3. Day after tomorrow"
                    ),
                    reply_markup=build_pickup_date_reply_markup(),
                )
            ]

        if selected_intent == "visit_history":
            mobile_for_history = derive_mobile_from_message(message, mobile)
            if not mobile_for_history:
                return [
                    OutgoingMessage(
                        text="I could not identify your mobile number for appointment history. Please share contact or send your mobile number.",
                        reply_markup=build_menu_reply_markup(client_type),
                    )
                ]

            return [
                OutgoingMessage(
                    text=build_visit_history_response(mobile_for_history),
                    reply_markup=build_menu_reply_markup(client_type),
                )
            ]

        if selected_intent == "order_status":
            mobile_for_order_status = derive_mobile_from_message(message, mobile)
            if not mobile_for_order_status:
                return [
                    OutgoingMessage(
                        text="I could not identify your mobile number for order status. Please share contact or send your mobile number.",
                        reply_markup=build_menu_reply_markup(client_type),
                    )
                ]

            return [
                OutgoingMessage(
                    text=build_order_status_response(mobile_for_order_status),
                    reply_markup=build_menu_reply_markup(client_type),
                )
            ]

        if selected_intent == "measurements":
            mobile_for_measurements = derive_mobile_from_message(message, mobile)
            if not mobile_for_measurements:
                return [
                    OutgoingMessage(
                        text="I could not identify your mobile number for saved measurements. Please share contact or send your mobile number.",
                        reply_markup=build_menu_reply_markup(client_type),
                    )
                ]

            return [
                OutgoingMessage(
                    text=build_measurements_response(mobile_for_measurements),
                    reply_markup=build_menu_reply_markup(client_type),
                )
            ]

        if selected_intent == "fabric_estimate":
            mobile_for_fabric = derive_mobile_from_message(message, mobile)
            if not mobile_for_fabric:
                return [
                    OutgoingMessage(
                        text="I could not identify your mobile number for fabric estimate request. Please share contact or send your mobile number.",
                        reply_markup=build_menu_reply_markup(client_type),
                    )
                ]

            fabric_result = raise_fabric_alert(mobile_for_fabric)
            handover_result = request_human_handover(mobile_for_fabric)

            if fabric_result.success and handover_result.success:
                return [
                    OutgoingMessage(
                        text=f"{fabric_result.message}\n{handover_result.message}",
                        reply_markup=build_menu_reply_markup(client_type),
                    )
                ]

            return [
                OutgoingMessage(
                    text=f"{fabric_result.message}\n{handover_result.message}",
                    reply_markup=build_menu_reply_markup(client_type),
                )
            ]

        if selected_intent == "handover":
            mobile_for_handover = derive_mobile_from_message(message, mobile)
            if not mobile_for_handover:
                return [
                    OutgoingMessage(
                        text="I could not identify your mobile number for human handover. Please share contact or send your mobile number.",
                        reply_markup=build_menu_reply_markup(client_type),
                    )
                ]

            handover_result = request_human_handover(mobile_for_handover)
            return [
                OutgoingMessage(
                    text=handover_result.message,
                    reply_markup=build_menu_reply_markup(client_type),
                )
            ]

        if selected_intent == "fabric_delivery":
            existing_session.awaiting_fabric_delivery_notes = True
            return [
                OutgoingMessage(
                    text=(
                        "Please share a short note for fabric delivery (optional).\n"
                        "Example: 3 meters of cotton fabric for a shirt.\n"
                        "Reply with 'skip' to continue without notes."
                    ),
                )
            ]

        if selected_intent == "order_changes":
            mobile_for_change = derive_mobile_from_message(message, mobile)
            if not mobile_for_change:
                return [
                    OutgoingMessage(
                        text="I could not identify your mobile number for order change request. Please share contact or send your mobile number.",
                        reply_markup=build_menu_reply_markup(client_type),
                    )
                ]

            clear_order_change_flow(existing_session)
            existing_session.awaiting_order_change_type = True
            return [OutgoingMessage(text=build_order_change_intro_message(mobile_for_change))]

        if selected_intent == "order_cancel":
            clear_order_cancel_flow(existing_session)
            existing_session.awaiting_order_cancel_reason = True
            return [
                OutgoingMessage(
                    text="Please share the reason for cancelling your current order.",
                )
            ]

        if selected_intent == "address_update":
            mobile_for_address = derive_mobile_from_message(message, mobile)
            if not mobile_for_address:
                return [
                    OutgoingMessage(
                        text="I could not identify your mobile number for address update. Please share contact or send your mobile number.",
                        reply_markup=build_menu_reply_markup(client_type),
                    )
                ]

            clear_address_update_flow(existing_session)
            existing_session.awaiting_address_action = True
            return [
                OutgoingMessage(
                    text=build_address_list_message(mobile_for_address),
                )
            ]

        intent_response = build_intent_response(selected_intent, client_type)
        if intent_response is not None:
            return intent_response

        return [OutgoingMessage(text=f"Selected option: {selected_intent}")]

    return []
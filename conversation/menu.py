SEGMENT_MENU_OPTIONS = {

    "active_client": {
        "1": {
            "label": "Track my order",
            "intent": "order_status"
        },
        "2": {
            "label": "Modify my order",
            "intent": "order_changes"
        },
        "3": {
            "label": "Cancel my order",
            "intent": "order_cancel"
        },
        "4": {
            "label": "Report an issue / Pickup alteration",
            "intent": "alteration_pickup_recent"
        },
        "5": {
            "label": "Book a store visit",
            "intent": "book_visit"
        },
        "6": {
            "label": "Place a new order / Schedule a pickup",
            "intent": "new_order"
        },
        "7": {
            "label": "Estimate fabric & price",
            "intent": "fabric_estimate"
        },
        "8": {
            "label": "View price catalogue",
            "intent": "pricing"
        }
    },

    "client": {
        "1": {
            "label": "Place an order / Schedule a pickup",
            "intent": "new_order"
        },
        "2": {
            "label": "Book a store visit",
            "intent": "book_visit"
        },
        "3": {
            "label": "View my measurements",
            "intent": "measurements"
        },
        "4": {
            "label": "View price catalogue",
            "intent": "pricing"
        },
        "5": {
            "label": "Estimate fabric & price",
            "intent": "fabric_estimate"
        },
        "6": {
            "label": "Drop off fabric at store",
            "intent": "fabric_delivery"
        },
        "7": {
            "label": "Report an issue / Pickup alteration",
            "intent": "alteration_pickup_recent"
        },
        "8": {
            "label": "Update my address & details",
            "intent": "address_update"
        }
    },

    "new_user": {
        "1": {
            "label": "Browse garments we stitch",
            "intent": "browse"
        },
        "2": {
            "label": "Learn how tailorsin.com works",
            "intent": "about"
        },
        "3": {
            "label": "Learn the measurement process",
            "intent": "measurement"
        },
        "4": {
            "label": "Check delivery timelines",
            "intent": "delivery"
        },
        "5": {
            "label": "View price catalogue",
            "intent": "pricing"
        },
        "6": {
            "label": "Check service areas",
            "intent": "service_area"
        },
        "7": {
            "label": "Book a store visit",
            "intent": "book_visit"
        },
        "8": {
            "label": "Register & place order",
            "intent": "register"
        }
    }

}


FOOTER_MENU_OPTIONS = {
    "9": {
        "label": "Chat with a human agent",
        "intent": "handover",
    },
    "0": {
        "label": "Go back to main menu",
        "intent": "main_menu",
    },
}

FOOTER_TEXT = (
    "\n\n--- Navigation ---\n"
    "9. Chat with a human agent\n"
    "0. Go back to the main menu"
)


KNOWN_CLIENT_TYPES = {"active_client", "client", "new_user"}


def normalize_client_type(client_type: str | None) -> str:
    if not client_type:
        return "new_user"

    normalized = client_type.strip().lower().replace(" ", "_")

    if normalized in KNOWN_CLIENT_TYPES:
        return normalized

    if "active" in normalized:
        return "active_client"

    if "client" in normalized:
        return "client"

    return "new_user"


def get_menu_options(client_type: str | None) -> dict:
    normalized_client_type = normalize_client_type(client_type)
    return SEGMENT_MENU_OPTIONS.get(normalized_client_type, SEGMENT_MENU_OPTIONS["new_user"])


def format_menu_message(client_type: str | None) -> str:
    return format_menu_message_with_greeting(client_type)


def format_menu_message_with_greeting(
    client_type: str | None,
    customer_salutation: str | None = None,
    is_repeat: bool = False,
) -> str:
    normalized_client_type = normalize_client_type(client_type)
    menu = get_menu_options(normalized_client_type)

    lines: list[str] = []

    if normalized_client_type in {"active_client", "client"}:
        salutation = customer_salutation or "valued customer"
        if is_repeat:
            lines.extend([
                "⏳ Your previous session ended due to inactivity.",
                "",
            ])

        lines.extend([
            "Hello 👋",
            f"Welcome back, {salutation}, to tailorsin.com!",
            "I'm your AI assistant. How may we assist you today?",
            "",
        ])
    else:
        lines.extend([
            "Hello there , welcome to tailorsin.com. Here are the best options to learn about our service and get started.",
            "",
        ])

    for option, item in menu.items():
        lines.append(f"{option}. {item['label']}")

    lines.append("")
    for option, item in FOOTER_MENU_OPTIONS.items():
        lines.append(f"{option}. {item['label']}")

    lines.extend([
        "",
        "Reply with the option number or tap a button below.",
    ])
    return "\n".join(lines)


def get_menu_keyboard(client_type: str | None) -> list[list[dict[str, str]]]:
    menu = get_menu_options(client_type)
    keyboard: list[list[dict[str, str]]] = []

    for option, item in menu.items():
        keyboard.append([
            {"text": f"{option}. {item['label']}"},
        ])

    keyboard.append([
        {"text": f"9. {FOOTER_MENU_OPTIONS['9']['label']}"},
        {"text": f"0. {FOOTER_MENU_OPTIONS['0']['label']}"},
    ])

    return keyboard


SEGMENT_MENU_OPTIONS = {

    "active_client": {
        "1": {
            "label": "Check the status of my current order",
            "intent": "order_status"
        },
        "2": {
            "label": "Start a new pickup/order request",
            "intent": "new_order"
        },
        "3": {
            "label": "Request changes to my current order",
            "intent": "order_changes"
        },
        "4": {
            "label": "Cancel my current order",
            "intent": "order_cancel"
        },
        "5": {
            "label": "View my saved measurements",
            "intent": "measurements"
        },
        "6": {
            "label": "Schedule a visit",
            "intent": "book_visit"
        },
        "7": {
            "label": "Get a fabric requirement and price estimate",
            "intent": "fabric_estimate"
        },
        "8": {
            "label": "View the price catalogue",
            "intent": "pricing"
        }

    },

    "client": {
        "1": {
            "label": "Schedule a pickup",
            "intent": "new_order"
        },
        "2": {
            "label": "View the price catalogue",
            "intent": "pricing"
        },
        "3": {
            "label": "Schedule a visit",
            "intent": "book_visit"
        },
        "4": {
            "label": "Get a fabric requirement and price estimate",
            "intent": "fabric_estimate"
        },
        "5": {
            "label": "View my saved measurements",
            "intent": "measurements"
        },
        "6": {
            "label": "Enquire about bulk orderss",
            "intent": "bulk_orders"
        },
        "7": {
            "label": "Arrange fabric delivery to our store",
            "intent": "fabric_delivery"
        },
        "8": {
            "label": "Update personal details",
            "intent": "address_update"
        }

    },

    "new_user": {
        "1": {
            "label": "Explore the garments we can stitch",
            "intent": "browse"
        },
        "2": {
            "label": "How tailorsin.com works",
            "intent": "about"
        },
        "3": {
            "label": "View the price catalogue",
            "intent": "pricing"
        },
        "4": {
            "label": "Understand our measurement process",
            "intent": "measurement"
        },
        "5": {
            "label": "Check delivery timelines",
            "intent": "delivery"
        },
        "6": {
            "label": "Check our service areas",
            "intent": "service_area"
        },
        "7": {
            "label": "Schedule a visit",
            "intent": "visit"
        },
        "8": {
            "label": "Register and place your first order",
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
        "label": "Go back to the main menu",
        "intent": "main_menu",
    },
}


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


"""
Menu configuration and formatting for the Tailorsin chatbot.

Provides structured menu options, formatted messages with emoji-enhanced
visual hierarchy, and keyboard layouts optimised for Telegram & WATI.
"""

from __future__ import annotations

# ──────────────────────────────────────────────
#  Emoji helpers
# ──────────────────────────────────────────────
_OPTION_ICONS: dict[str, str] = {
    # Orders
    "order_status": "🔍",
    "order_changes": "✏️",
    "order_cancel": "🚫",
    # Support
    "alteration_pickup_recent": "🔄",
    "handover": "💬",
    # Services
    "new_order": "➕",
    "fabric_estimate": "📐",
    "fabric_delivery": "📦",
    "book_visit": "📅",
    # Info
    "pricing": "💰",
    "browse": "👗",
    "about": "ℹ️",
    "measurement": "📏",
    "delivery": "🚚",
    "service_area": "📍",
    # Account
    "measurements": "📋",
    "address_update": "🏠",
    "register": "📝",
    # Navigation
    "main_menu": "🏠",
}


def _icon(intent: str) -> str:
    return _OPTION_ICONS.get(intent, "•")


# ──────────────────────────────────────────────
#  Menu data
# ──────────────────────────────────────────────

SEGMENT_MENU_OPTIONS: dict[str, dict[str, dict[str, str]]] = {

    "active_client": {
        "1":  {"label": "Track my order",              "intent": "order_status"},
        "2":  {"label": "Modify my order",              "intent": "order_changes"},
        "3":  {"label": "Cancel my order",              "intent": "order_cancel"},
        "4":  {"label": "Report an issue / Alteration", "intent": "alteration_pickup_recent"},
        "5":  {"label": "Book a store visit",           "intent": "book_visit"},
        "6":  {"label": "Place a new order / Pickup",   "intent": "new_order"},
        "7":  {"label": "Estimate fabric & price",      "intent": "fabric_estimate"},
        "8":  {"label": "View price catalogue",         "intent": "pricing"},
    },

    "client": {
        "1":  {"label": "Place an order / Pickup",      "intent": "new_order"},
        "2":  {"label": "Book a store visit",           "intent": "book_visit"},
        "3":  {"label": "View my measurements",         "intent": "measurements"},
        "4":  {"label": "View price catalogue",         "intent": "pricing"},
        "5":  {"label": "Estimate fabric & price",      "intent": "fabric_estimate"},
        "6":  {"label": "Drop off fabric at store",     "intent": "fabric_delivery"},
        "7":  {"label": "Report an issue / Alteration", "intent": "alteration_pickup_recent"},
        "8":  {"label": "Update my address",            "intent": "address_update"},
    },

    "new_user": {
        "1":  {"label": "Browse garments we stitch",    "intent": "browse"},
        "2":  {"label": "How tailorsin.com works",      "intent": "about"},
        "3":  {"label": "Learn the measurement process", "intent": "measurement"},
        "4":  {"label": "Check delivery timelines",     "intent": "delivery"},
        "5":  {"label": "View price catalogue",         "intent": "pricing"},
        "6":  {"label": "Check service areas",          "intent": "service_area"},
        "7":  {"label": "Book a store visit",           "intent": "book_visit"},
        "8":  {"label": "Register & place order",       "intent": "register"},
    },
}

FOOTER_MENU_OPTIONS: dict[str, dict[str, str]] = {
    "9": {"label": "Chat with a human agent", "intent": "handover"},
    "0": {"label": "Go back to main menu",    "intent": "main_menu"},
}

KNOWN_CLIENT_TYPES: set[str] = {"active_client", "client", "new_user"}

# Enhanced footer text for sub-flows (used via with_footer() in conversation_service)
FOOTER_TEXT = (
    "\n\n━━━ Navigation ━━━\n"
    "9. 💬 Chat with a human agent\n"
    "0. 🏠 Go back to the main menu"
)


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def normalize_client_type(client_type: str | None) -> str:
    """Map a raw client-type string to one of the known keys."""
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


def get_menu_options(client_type: str | None) -> dict[str, dict[str, str]]:
    """Return the menu dict for the given (normalised) client type."""
    normalized = normalize_client_type(client_type)
    return SEGMENT_MENU_OPTIONS.get(normalized, SEGMENT_MENU_OPTIONS["new_user"])


# ──────────────────────────────────────────────
#  Formatted text messages
# ──────────────────────────────────────────────

def format_menu_message(client_type: str | None) -> str:
    """Shortcut – delegates to the full greeting builder."""
    return format_menu_message_with_greeting(client_type)


def format_menu_message_with_greeting(
    client_type: str | None,
    customer_salutation: str | None = None,
    is_repeat: bool = False,
) -> str:
    """Build a polished, emoji-rich menu message for the given client segment."""
    normalized = normalize_client_type(client_type)
    menu = get_menu_options(normalized)

    lines: list[str] = []

    # ── Greeting ──────────────────────────────────
    if normalized in {"active_client", "client"}:
        salutation = customer_salutation or "valued customer"

        if is_repeat:
            lines.append("⏳ *Your previous session ended due to inactivity.*")
            lines.append("")

        lines.extend([
            "👋 *Welcome back!*",
            f"Hello {salutation}, great to see you again at **tailorsin.com** ✨",
            "",
            "I'm your AI assistant. How can I help you today?",
            "",
        ])
    else:
        lines.extend([
            "👋 *Welcome to tailorsin.com!*",
            "",
            "We bring professional tailoring to your doorstep. "
            "Here's everything you can do to get started 👇",
            "",
        ])

    # ── Menu items ────────────────────────────────
    for option, item in menu.items():
        icon = _icon(item["intent"])
        lines.append(f"  {option}. {icon} {item['label']}")

    lines.append("")

    # ── Footer items ──────────────────────────────
    for option, item in FOOTER_MENU_OPTIONS.items():
        icon = _icon(item["intent"])
        lines.append(f"  {option}. {icon} {item['label']}")

    lines.extend([
        "",
        "—",
        f"Reply with the option number, or tap a button below ⬇️",
    ])

    return "\n".join(lines)


# ──────────────────────────────────────────────
#  Keyboard layouts (Telegram / WATI)
# ──────────────────────────────────────────────

def get_menu_keyboard(client_type: str | None) -> list[list[dict[str, str]]]:
    """
    Return a 2‑column keyboard layout for the given client segment.

    Each row holds up to 2 buttons (except the footer row which is 2 wide).
    """
    menu = get_menu_options(client_type)
    keyboard: list[list[dict[str, str]]] = []

    # Group main options in pairs (2 columns)
    items = list(menu.items())
    for i in range(0, len(items), 2):
        row: list[dict[str, str]] = []
        for j in range(2):
            if i + j < len(items):
                option, item = items[i + j]
                icon = _icon(item["intent"])
                row.append({"text": f"{option}. {icon} {item['label']}"})
        keyboard.append(row)

    # Footer row
    keyboard.append([
        {"text": f"9. {_icon('handover')} {FOOTER_MENU_OPTIONS['9']['label']}"},
        {"text": f"0. {_icon('main_menu')} {FOOTER_MENU_OPTIONS['0']['label']}"},
    ])

    return keyboard
import re

from conversation.menu import FOOTER_MENU_OPTIONS, get_menu_options


VISIT_HISTORY_INPUTS = {
    "visit history",
    "appointment history",
    "visit status",
    "appointment status",
    "my appointments",
}

# Regex to strip common emoji characters so button taps with emojis still match.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # misc
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002600-\U000026FF"  # misc symbols
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero-width joiner
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """Remove emoji characters from *text* so plain-label matching still works.

    Whitespace is also normalised (emoji removal can leave double spaces, e.g.
    "9. 💬 Chat" -> "9.  Chat") so that button-tap text matches single-space
    menu candidates.
    """
    cleaned = _EMOJI_PATTERN.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def get_intent(client_type, option):

    menu = get_menu_options(client_type)

    normalized_option = option.strip()
    if normalized_option.casefold() in VISIT_HISTORY_INPUTS:
        return "visit_history"

    if normalized_option in menu:
        return menu[normalized_option]["intent"]

    # Also try matching after stripping emojis (for button taps).
    plain_option = _strip_emoji(normalized_option)

    for menu_option, item in menu.items():
        label = item["label"]
        candidates = {
            label.casefold(),
            f"{menu_option}. {label}".casefold(),
        }
        if normalized_option.casefold() in candidates or plain_option.casefold() in candidates:
            return item["intent"]
        # Fallback: button text such as "1. 🔍 Track my order" always begins
        # with the option number, so accept it even if the label wording differs.
        if plain_option.casefold().startswith(f"{menu_option}. "):
            return item["intent"]

    for menu_option, item in FOOTER_MENU_OPTIONS.items():
        label = item["label"]
        candidates = {
            menu_option.casefold(),
            label.casefold(),
            f"{menu_option}. {label}".casefold(),
        }
        if normalized_option.casefold() in candidates or plain_option.casefold() in candidates:
            return item["intent"]
        if plain_option.casefold().startswith(f"{menu_option}. "):
            return item["intent"]

    if normalized_option == "10":
        return FOOTER_MENU_OPTIONS["0"]["intent"]

    return None

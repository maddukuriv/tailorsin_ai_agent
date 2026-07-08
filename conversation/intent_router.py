from conversation.menu import FOOTER_MENU_OPTIONS, get_menu_options


VISIT_HISTORY_INPUTS = {
    "visit history",
    "appointment history",
    "visit status",
    "appointment status",
    "my appointments",
}


def get_intent(client_type, option):

    menu = get_menu_options(client_type)

    normalized_option = option.strip()
    if normalized_option.casefold() in VISIT_HISTORY_INPUTS:
        return "visit_history"

    if normalized_option in menu:
        return menu[normalized_option]["intent"]

    for menu_option, item in menu.items():
        label = item["label"]
        if normalized_option.casefold() in {
            label.casefold(),
            f"{menu_option}. {label}".casefold(),
        }:
            return item["intent"]

    for menu_option, item in FOOTER_MENU_OPTIONS.items():
        label = item["label"]
        if normalized_option.casefold() in {
            menu_option.casefold(),
            label.casefold(),
            f"{menu_option}. {label}".casefold(),
        }:
            return item["intent"]

    if normalized_option == "10":
        return FOOTER_MENU_OPTIONS["0"]["intent"]

    return None
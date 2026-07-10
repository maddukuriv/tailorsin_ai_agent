from crm.items_with_price import fetch_price_catalog


MAX_MESSAGE_LENGTH = 3500


def _resolve_catalog_category(client_type: str) -> int:
    normalized = (client_type or "").strip().lower()
    if normalized == "active_client":
        return 6
    if normalized == "client":
        return 6
    return 6


async def build_pricing_response(client_type: str) -> str:
    category_id = _resolve_catalog_category(client_type)
    catalog = await fetch_price_catalog(catid=category_id)

    if not catalog.success:
        return catalog.message

    lines: list[str] = [
        f"Price Catalogue ({catalog.category_label})",
        "",
    ]

    for item in catalog.items:
        lines.append(f"{item.item_name}:")
        for subitem in item.subitems:
            tax_text = f" + Tax {subitem.tax}%" if subitem.tax else ""
            lines.append(f"- {subitem.subitem_name}: Rs.{subitem.price}{tax_text}")
        lines.append("")

    lines.append("Reply with 0 for main menu or 9 to chat with a human agent.")
    message = "\n".join(lines)

    if len(message) > MAX_MESSAGE_LENGTH:
        truncated = message[:MAX_MESSAGE_LENGTH].rstrip()
        return f"{truncated}\n\n...Catalogue is long. Reply with main menu to continue browsing options."

    return message
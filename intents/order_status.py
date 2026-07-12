from crm.order_status import fetch_all_active_orders


async def build_order_status_response(mobile: str) -> str:
    result = await fetch_all_active_orders(mobile)
    if not result.success:
        return result.message

    if not result.orders:
        return result.message

    heading = "Your Active Orders"
    if result.customer_name:
        heading = f"{heading} ({result.customer_name})"

    lines: list[str] = [
        heading,
        "",
    ]

    for index, order in enumerate(result.orders, start=1):
        lines.append(f"{index}. Order #{order.order_id} — {order.stage_label}")
        if order.order_date:
            lines.append(f"   Order Date: {order.order_date}")
        if order.pickup_date:
            pickup_line = f"   Pickup Date: {order.pickup_date}"
            if order.pickup_time:
                pickup_line = f"{pickup_line} ({order.pickup_time})"
            lines.append(pickup_line)
        if order.last_update_date:
            lines.append(f"   Last Update: {order.last_update_date}")
        lines.append("")

    lines.extend([
        "Reply with 0 for main menu or 9 to chat with a human agent.",
    ])
    return "\n".join(lines)

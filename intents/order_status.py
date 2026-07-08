from crm.order_status import fetch_current_order_status


def build_order_status_response(mobile: str) -> str:
    result = fetch_current_order_status(mobile)
    if not result.success:
        return result.message

    if result.order is None:
        return result.message

    heading = "Current Order Status"
    if result.customer_name:
        heading = f"{heading} ({result.customer_name})"

    lines: list[str] = [
        heading,
        "",
        f"Order ID: {result.order.order_id}",
        f"Stage: {result.order.stage_label}",
    ]

    if result.order.order_date:
        lines.append(f"Order Date: {result.order.order_date}")

    if result.order.pickup_date:
        pickup_line = f"Pickup Date: {result.order.pickup_date}"
        if result.order.pickup_time:
            pickup_line = f"{pickup_line} ({result.order.pickup_time})"
        lines.append(pickup_line)

    if result.order.last_update_date:
        lines.append(f"Last Update: {result.order.last_update_date}")

    lines.extend([
        "",
        "Reply with 0 for main menu or 9 to chat with a human agent.",
    ])
    return "\n".join(lines)

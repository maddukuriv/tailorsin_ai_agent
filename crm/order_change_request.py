from dataclasses import dataclass

import requests


BASE_URL = "https://crm.tailorsin.com/tailorsin-api/api/orderchangerequest.php"
MAX_DETAILS_LENGTH = 1000


@dataclass
class OrderChangeRequestItem:
    request_id: int | None
    order_id: int | None
    request_type: str
    details: str
    status_label: str
    created_at: str


@dataclass
class OrderChangeRequestListResult:
    success: bool
    message: str
    requests: list[OrderChangeRequestItem]


@dataclass
class OrderChangeRequestCreateResult:
    success: bool
    message: str
    request_id: int | None = None
    order_id: int | None = None


def _clean(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())


def _to_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def list_order_change_requests(mobile: str) -> OrderChangeRequestListResult:
    try:
        response = requests.get(BASE_URL, params={"mobile": mobile}, timeout=20)
        payload = response.json() if response.content else {}
    except Exception:
        return OrderChangeRequestListResult(
            success=False,
            message="Unable to fetch order change requests right now. Please try again shortly.",
            requests=[],
        )

    if response.status_code >= 400 or str(payload.get("status", "")).lower() != "success":
        return OrderChangeRequestListResult(
            success=False,
            message=str(payload.get("message") or "Unable to fetch order change requests."),
            requests=[],
        )

    request_payload = payload.get("requests") if isinstance(payload.get("requests"), list) else []
    requests_list: list[OrderChangeRequestItem] = []

    for item in request_payload:
        if not isinstance(item, dict):
            continue

        requests_list.append(
            OrderChangeRequestItem(
                request_id=_to_int(item.get("id") or item.get("request_id")),
                order_id=_to_int(item.get("order_id")),
                request_type=_clean(item.get("request_type")) or "other",
                details=_clean(item.get("details")),
                status_label=_clean(item.get("status_label")) or _clean(item.get("status")) or "Pending",
                created_at=_clean(item.get("created_at")),
            )
        )

    return OrderChangeRequestListResult(
        success=True,
        message="Order change request history fetched successfully.",
        requests=requests_list,
    )


def create_order_change_request(
    mobile: str,
    request_type: str,
    details: str,
    order_id: int | None = None,
) -> OrderChangeRequestCreateResult:
    cleaned_details = details.strip()
    if len(cleaned_details) > MAX_DETAILS_LENGTH:
        cleaned_details = cleaned_details[:MAX_DETAILS_LENGTH].rstrip()

    payload: dict[str, object] = {
        "mobile": mobile,
        "request_type": request_type,
        "details": cleaned_details,
    }
    if order_id is not None:
        payload["order_id"] = order_id

    try:
        response = requests.post(BASE_URL, json=payload, timeout=20)
        data = response.json() if response.content else {}
    except Exception:
        return OrderChangeRequestCreateResult(
            success=False,
            message="Unable to submit order change request right now. Please try again shortly.",
        )

    if response.status_code == 200 and str(data.get("status", "")).lower() == "success":
        response_data = data.get("data") if isinstance(data.get("data"), dict) else {}
        return OrderChangeRequestCreateResult(
            success=True,
            message=str(data.get("message") or "your request has been recorded, our team will get back to you shortly"),
            request_id=_to_int(response_data.get("request_id") or response_data.get("id")),
            order_id=_to_int(response_data.get("order_id")),
        )

    return OrderChangeRequestCreateResult(
        success=False,
        message=str(data.get("message") or "Unable to submit order change request."),
    )

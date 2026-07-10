from dataclasses import dataclass

from services.http_client import http_get


BASE_URL = "https://crm.tailorsin.com/tailorsin-api/api/orderstatus.php"


@dataclass
class CurrentOrderDetails:
	order_id: str
	stage_label: str
	order_date: str
	last_update_date: str
	pickup_date: str | None
	pickup_time: str | None


@dataclass
class CurrentOrderStatusResult:
	success: bool
	message: str
	customer_name: str | None
	order: CurrentOrderDetails | None


def _clean(value: object) -> str:
	if not isinstance(value, str):
		return ""
	return " ".join(value.strip().split())


def _pickup_time_label(value: str | None) -> str | None:
	if value == "1":
		return "9 AM - 2 PM"
	if value == "2":
		return "2 PM - 9 PM"
	if value:
		return value
	return None


async def fetch_current_order_status(mobile: str) -> CurrentOrderStatusResult:
	try:
		response = await http_get(BASE_URL, params={"mobile": mobile})
		payload = response.json() if response.content else {}
	except Exception:
		return CurrentOrderStatusResult(
			success=False,
			message="Unable to fetch your current order status right now. Please try again shortly.",
			customer_name=None,
			order=None,
		)

	if str(payload.get("status", "")).lower() != "success":
		return CurrentOrderStatusResult(
			success=False,
			message=str(payload.get("message") or "Unable to fetch current order status."),
			customer_name=None,
			order=None,
		)

	client_payload = payload.get("client") if isinstance(payload.get("client"), dict) else {}
	customer_name = _clean(client_payload.get("cname")) or None

	order_payload = payload.get("data") if isinstance(payload.get("data"), dict) else None
	if order_payload is None:
		return CurrentOrderStatusResult(
			success=True,
			message=str(payload.get("message") or "No current open order found."),
			customer_name=customer_name,
			order=None,
		)

	pickup_time_raw = _clean(order_payload.get("pickup_time"))
	order = CurrentOrderDetails(
		order_id=str(order_payload.get("order_id") or ""),
		stage_label=_clean(order_payload.get("stage_label")) or "Unknown",
		order_date=_clean(order_payload.get("order_date")),
		last_update_date=_clean(order_payload.get("last_update_date")),
		pickup_date=_clean(order_payload.get("pickup_date")) or None,
		pickup_time=_pickup_time_label(pickup_time_raw),
	)

	return CurrentOrderStatusResult(
		success=True,
		message="Current order status fetched successfully.",
		customer_name=customer_name,
		order=order,
	)
import time
from dataclasses import dataclass, field


@dataclass
class SessionState:
	chat_id: int
	mobile: str | None = None
	client_type: str | None = None
	customer_salutation: str | None = None
	awaiting_contact: bool = False
	has_seen_known_customer_menu: bool = False
	awaiting_registration_name: bool = False
	awaiting_pickup_date: bool = False
	awaiting_pickup_time: bool = False
	awaiting_alteration_pickup_notes: bool = False
	pending_pickup_date: str | None = None
	pending_pickup_time: int | None = None
	pickup_mode: str | None = None
	awaiting_visit_date: bool = False
	awaiting_visit_time: bool = False
	pending_visit_date: str | None = None
	pending_visit_slots: list[str] = field(default_factory=list)
	awaiting_fabric_delivery_notes: bool = False
	awaiting_address_action: bool = False
	awaiting_address_add_line: bool = False
	awaiting_address_add_city: bool = False
	awaiting_address_add_pincode: bool = False
	awaiting_address_update_id: bool = False
	awaiting_address_update_line: bool = False
	awaiting_address_set_main: bool = False
	awaiting_address_delete_id: bool = False
	awaiting_pickup_address: bool = False
	pending_pickup_address_id: int | None = None
	pending_address_ordered_ids: list[int] = field(default_factory=list)
	pending_address_list_ids: list[int] = field(default_factory=list)
	awaiting_order_change_type: bool = False
	awaiting_order_change_details: bool = False
	awaiting_order_cancel_reason: bool = False
	pending_order_change_type: str | None = None
	pending_address_line: str | None = None
	pending_address_city: str | None = None
	pending_address_id: int | None = None
	address_needed_for_pickup: bool = False
	last_activity_at: float = field(default_factory=time.time)


_SESSIONS: dict[int, SessionState] = {}


def get_session(chat_id: int) -> SessionState:
	session = _SESSIONS.get(chat_id)
	if session is None:
		session = SessionState(chat_id=chat_id)
		_SESSIONS[chat_id] = session
	return session


def reset_session(chat_id: int) -> SessionState:
	session = SessionState(chat_id=chat_id)
	_SESSIONS[chat_id] = session
	return session

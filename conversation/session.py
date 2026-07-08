from dataclasses import dataclass


@dataclass
class SessionState:
	chat_id: int
	mobile: str | None = None
	client_type: str | None = None
	customer_salutation: str | None = None
	awaiting_contact: bool = False
	has_seen_known_customer_menu: bool = False


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

from conversation.session import get_session, reset_session


def mark_awaiting_contact(chat_id: int) -> None:
	session = get_session(chat_id)
	session.awaiting_contact = True


def save_client_profile(
	chat_id: int,
	mobile: str | None,
	client_type: str,
	customer_salutation: str | None = None,
) -> None:
	session = get_session(chat_id)
	session.mobile = mobile
	session.client_type = client_type
	session.customer_salutation = customer_salutation
	session.awaiting_contact = False


def get_client_profile(chat_id: int) -> tuple[str | None, str | None, str | None]:
	session = get_session(chat_id)
	return session.mobile, session.client_type, session.customer_salutation


__all__ = [
	"get_client_profile",
	"get_session",
	"mark_awaiting_contact",
	"reset_session",
	"save_client_profile",
]

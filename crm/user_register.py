from dataclasses import dataclass
import logging

import requests


BASE_URL = "https://crm.tailorsin.com/tailorsin-api/api/addclient.php"
logger = logging.getLogger(__name__)


@dataclass
class RegistrationResult:
	success: bool
	message: str


def _mask_mobile(mobile: str) -> str:
	digits_only = "".join(character for character in mobile if character.isdigit())
	if len(digits_only) <= 4:
		return digits_only
	return f"***{digits_only[-4:]}"


def register_new_client(mobile: str, name: str | None = None) -> RegistrationResult:
	try:
		payload = {"mobile": mobile}
		if name:
			payload["cname"] = name

		response = requests.post(BASE_URL, json=payload, timeout=20)
		data = response.json()

		logger.info(
			"register_new_client request mobile=%s has_name=%s status_code=%s",
			_mask_mobile(mobile),
			bool(name),
			response.status_code,
		)

		if response.status_code >= 400:
			return RegistrationResult(
				success=False,
				message=data.get("message", "Unable to register right now. Please try again."),
			)

		status = str(data.get("status", "")).strip().lower()
		if status == "success":
			return RegistrationResult(
				success=True,
				message=data.get("message", "You are registered successfully."),
			)

		return RegistrationResult(
			success=False,
			message=data.get("message", "Unable to register right now. Please try again."),
		)

	except Exception:
		logger.exception(
			"register_new_client exception mobile=%s has_name=%s",
			_mask_mobile(mobile),
			bool(name),
		)
		return RegistrationResult(
			success=False,
			message="Unable to register right now. Please try again.",
		)

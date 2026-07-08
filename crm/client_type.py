from dataclasses import dataclass

import requests

BASE_URL = "https://crm.tailorsin.com/tailorsin-api/api/getclient"


@dataclass
class CustomerProfile:
    client_type: str
    customer_salutation: str | None = None


def _first_non_empty(data: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_customer_salutation(data: dict) -> str | None:
    salutation = _first_non_empty(data, ("customer_salutation", "salutation", "title", "prefix"))
    full_name = _first_non_empty(data, ("customer_name", "full_name", "display_name", "name"))

    if full_name is None:
        first_name = _first_non_empty(data, ("first_name", "firstname", "firstName"))
        last_name = _first_non_empty(data, ("last_name", "lastname", "lastName"))
        if first_name or last_name:
            full_name = " ".join(part for part in (first_name, last_name) if part)

    if salutation and full_name:
        return f"{salutation} {full_name}".strip()

    return full_name or salutation


def lookup_customer_profile(mobile: str) -> CustomerProfile:

    try:

        response = requests.get(
            BASE_URL,
            params={"mobile": mobile},
            timeout=10
        )

        if response.status_code != 200:
            return CustomerProfile(client_type="new_user")

        data = response.json()

        return CustomerProfile(
            client_type=data.get("client_type", "new_user"),
            customer_salutation=_build_customer_salutation(data),
        )

    except Exception as e:
        print(e)
        return CustomerProfile(client_type="new_user")


def get_client_type(mobile: str):
    return lookup_customer_profile(mobile).client_type
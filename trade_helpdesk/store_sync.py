import frappe
from frappe.contacts.doctype.contact.contact import get_contact_name
from frappe.core.doctype.user.user import create_contact
from frappe.utils.oauth import get_email

MANAGER_ROLE_FLAG = 1
MEMBER_ROLE_FLAG = 0


def sync_stores(info: dict) -> None:
    """Mirror the `stores` claim as HD Customers and link the user's Contact.

    Never raises. A failure here must not break the login: the user is already
    authenticated by the time this runs, and support access matters less than
    getting them in.
    """
    try:
        _sync(info)
    except Exception:
        frappe.log_error(
            title="Trade store sync failed",
            message=frappe.get_traceback(with_context=True),
        )


def _sync(info: dict) -> None:
    stores = info.get("stores") or []
    if not stores:
        # Also the shape a store-service outage produces, so this is treated as
        # "nothing to add" and never as "remove their memberships".
        return

    email = get_email(info)
    if not email:
        return

    contact_name = _ensure_contact(email)
    if not contact_name:
        return

    for store in stores:
        _link_to_customer(store, contact_name)


def _ensure_contact(email: str) -> str | None:
    """Frappe enqueues Contact creation after commit, so it may not exist yet.

    create_contact is idempotent - it updates an existing Contact rather than
    duplicating it - so calling it here just brings the creation forward.
    """
    contact_name = get_contact_name(email)
    if contact_name:
        return contact_name

    create_contact(frappe.get_doc("User", email), ignore_mandatory=True)
    return get_contact_name(email)


def _link_to_customer(store: dict, contact_name: str) -> None:
    customer_name = store.get("name")
    if not customer_name:
        return

    if not frappe.db.exists("HD Customer", customer_name):
        frappe.get_doc(
            {"doctype": "HD Customer", "customer_name": customer_name}
        ).insert(ignore_permissions=True)

    customer = frappe.get_doc("HD Customer", customer_name)
    if any(row.contact_name == contact_name for row in customer.contacts):
        return

    # Appended directly rather than through add_contacts(): that method demands
    # System Manager or Agent Manager, and this runs as the seller who just
    # logged in, who has neither.
    customer.append(
        "contacts",
        {
            "contact_name": contact_name,
            "is_manager": MANAGER_ROLE_FLAG
            if store.get("is_owner")
            else MEMBER_ROLE_FLAG,
        },
    )
    customer.save(ignore_permissions=True)

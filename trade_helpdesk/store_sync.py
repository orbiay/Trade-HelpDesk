import frappe
from frappe.contacts.doctype.contact.contact import get_contact_name
from frappe.core.doctype.user.user import create_contact
from frappe.utils.oauth import get_email

IS_MANAGER = 1
IS_MEMBER = 0


def sync_stores(info: dict) -> None:
    """Mirror the `stores` claim as HD Customers and link the user's Contact.

    Runs synchronously inside the OAuth callback and owns its own transaction
    boundary. `login_oauth_user` has already committed the User and the session
    by this point, so a rollback here cannot un-authenticate anyone - it only
    discards half-written customers and memberships.

    Never raises: the user is authenticated either way, and support access
    matters less than letting them in.
    """
    stores = info.get("stores") or []
    if not stores:
        # Also what a Trade store-service outage looks like, so it means
        # "nothing to add" and never "remove their memberships".
        return

    try:
        _sync(info, stores)
        # The callback is a GET, so nothing commits this for us.
        frappe.db.commit()
    except Exception:
        # Leaves no customer created without its membership, or vice versa.
        frappe.db.rollback()
        frappe.log_error(
            title="Trade store sync failed",
            message=frappe.get_traceback(with_context=True),
        )
        # The rollback above discarded the Error Log row along with everything
        # else, so it needs its own commit.
        frappe.db.commit()


def _sync(info: dict, stores: list[dict]) -> None:
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

    `create_contact` is idempotent in the installed version - it looks the
    Contact up by email and updates it rather than duplicating - so calling it
    here only brings that work forward into this request.
    """
    contact_name = get_contact_name(email)
    if contact_name:
        return contact_name

    create_contact(frappe.get_doc("User", email), ignore_mandatory=True)
    return get_contact_name(email)


def _link_to_customer(store: dict, contact_name: str) -> None:
    """Create the customer if new, then link the contact exactly once.

    The store name is the customer's identity, because `HD Customer` is named
    by `customer_name` and the installed version has no field to hold Trade's
    store id.
    """
    customer_name = store.get("name")
    if not customer_name:
        return

    if not frappe.db.exists("HD Customer", customer_name):
        # helpdesk.api.customer.create_customer cannot be used: it opens with
        # frappe.has_permission("HD Customer", "create", throw=True), and the
        # HD Customer role that every SSO seller receives has no create
        # permission. Inserting the document directly is the same operation
        # without that check.
        frappe.get_doc(
            {"doctype": "HD Customer", "customer_name": customer_name}
        ).insert(ignore_permissions=True)

    customer = frappe.get_doc("HD Customer", customer_name)
    is_manager = IS_MANAGER if store.get("is_owner") else IS_MEMBER

    existing = next(
        (row for row in customer.contacts if row.contact_name == contact_name), None
    )

    if existing:
        if existing.is_manager == is_manager:
            # Already linked with the right flag; saving would be a no-op write.
            return
        existing.is_manager = is_manager
    else:
        # Appended directly rather than through add_contacts(): that method
        # demands System Manager or Agent Manager, and this runs as the seller
        # who just logged in, who has neither.
        customer.append(
            "contacts", {"contact_name": contact_name, "is_manager": is_manager}
        )

    # HD Customer.before_save -> handle_roles() grants or revokes the
    # "HD Customer Manager" role from this flag, so the save keeps Helpdesk's
    # own role logic in charge.
    customer.save(ignore_permissions=True)

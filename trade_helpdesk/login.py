import frappe
from frappe.integrations.oauth2_logins import decoder_compat
from frappe.utils.oauth import get_info_via_oauth, login_oauth_user

from trade_helpdesk.store_sync import sync_stores


@frappe.whitelist(allow_guest=True)
def custom(code: str, state: str):
    """OAuth callback for user-defined providers.

    Mirrors `frappe.integrations.oauth2_logins.custom` exactly, with one
    addition: the claim set is held on to so the user's Trade stores can be
    mirrored afterwards. Frappe's version passes the claims straight into
    `login_via_oauth2`, which keeps them on the stack and discards the rest.

    The callback path carries the provider, so this is still reachable at
    /api/method/frappe.integrations.oauth2_logins.custom/<provider>.
    """
    path = frappe.request.path[1:].split("/")
    if len(path) != 4 or not path[3]:
        return

    provider = path[3]
    if not frappe.db.exists("Social Login Key", provider):
        return

    info = get_info_via_oauth(provider, code, decoder_compat)
    login_oauth_user(info, provider=provider, state=state)

    # login_oauth_user returns without logging anyone in when the state is
    # stale or signups are disabled; it renders its own error page instead.
    if frappe.session.user and frappe.session.user != "Guest":
        sync_stores(info)

import frappe
from frappe.integrations.oauth2_logins import decoder_compat
from frappe.utils.oauth import get_info_via_oauth, login_oauth_user

from trade_helpdesk.store_sync import sync_stores

# Only this provider carries a `stores` claim. Any other custom provider keeps
# Frappe's stock behaviour.
TRADE_PROVIDER = "trade"


@frappe.whitelist(allow_guest=True)
def custom(code: str, state: str):
    """OAuth callback for user-defined providers.

    Mirrors `frappe.integrations.oauth2_logins.custom` exactly, with one
    addition: the claim set is held on to so the user's Trade stores can be
    mirrored afterwards. Frappe's version hands the claims straight to
    `login_via_oauth2`, which keeps them on the stack and drops the rest.

    The callback path still carries the provider, so this remains reachable at
    /api/method/frappe.integrations.oauth2_logins.custom/<provider>.
    """
    path = frappe.request.path[1:].split("/")
    if len(path) != 4 or not path[3]:
        return

    provider = path[3]
    if not frappe.db.exists("Social Login Key", provider):
        return

    info = get_info_via_oauth(provider, code, decoder_compat)

    # Commits the User and the session, then sets the redirect on
    # frappe.local.response. Everything below runs inside the same request, so
    # the sync finishes before that redirect is sent.
    login_oauth_user(info, provider=provider, state=state)

    # Returns without logging anyone in when the state is stale or signups are
    # disabled - it renders its own error page instead.
    if provider == TRADE_PROVIDER and frappe.session.user not in (None, "Guest"):
        sync_stores(info)

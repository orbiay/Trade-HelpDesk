# Trade Helpdesk

Bridges Trade SSO into Frappe Helpdesk's customer model.

Frappe's own OAuth handler reads only the standard claims and discards the rest,
so the `stores` claim Trade sends is invisible to it. This app replaces that one
handler with an identical version that keeps the claims, then mirrors each store
as an `HD Customer` and links the user's `Contact` to it.

Everything else about the login is unchanged.

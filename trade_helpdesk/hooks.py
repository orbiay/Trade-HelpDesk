app_name = "trade_helpdesk"
app_title = "Trade Helpdesk"
app_publisher = "Trade"
app_description = "Mirrors Trade stores as Helpdesk customers during SSO login"
app_email = "trade@dice.ma"
app_license = "MIT"

# Frappe's own handler (frappe.integrations.oauth2_logins.custom) reads only the
# standard claims and drops everything else, so the `stores` claim Trade sends
# never reaches any code. This swaps in an identical handler that keeps them.
#
# Supported by frappe/__init__.py:2555 - not a patch of Frappe's source.
override_whitelisted_methods = {
    "frappe.integrations.oauth2_logins.custom": "trade_helpdesk.login.custom"
}

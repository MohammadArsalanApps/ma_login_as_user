# Login as Any User (Odoo 20.0)

This on-premise add-on lets explicitly authorized administrators open an eligible user's Odoo session and return to their original account. The target user remains the effective Odoo user: record rules, access rights, chatter attribution, and `create_uid` / `write_uid` operate as that user. Every switch creates a read-only audit event.

## Supported environment

- This branch targets Odoo 20.0 on-premise (Community or Enterprise); it has no Enterprise-only dependency.
- The module requires an already authenticated manager session and does not disable or bypass Odoo's configured multi-factor authentication.
- Odoo core's Lunch app has a feature-specific manager-only impersonation check; the inspected build did not contain a general user-switch tool.
- The 20.0 branch uses Odoo 20's JSON-RPC route and frontend RPC APIs. Use the matching branch for other Odoo major versions.

## Installation and setup

1. Copy `ma_login_as_user` into an on-premise addons path, update the Apps list, and install it.
2. The post-install hook grants the built-in administrator the Impersonation Manager group once and records that grant in server logs.
3. Review Settings > General Settings > Login as Any User. Add additional managers and auditors through Settings > Users & Companies > Users.
4. Enable the manager group only for staff authorized under the organization's access and data-protection policy. A server configuration kill switch can be set as `ma_login_as_user_enabled = False` in `odoo.conf`; it overrides the database setting.

## Usage

- Use the user-secret icon in the backend systray, or the Login as this user button on a user form. A list contextual action is available for one selected user.
- Search supports name, login, and email. Users can be pinned as favorites, and the five most recently switched accounts are shown.
- A persistent amber banner identifies the target and original administrator, shows elapsed time, and offers Return to my account.
- While switched, selecting another account always attributes the new audit event to the original administrator. The target cannot become the new administrator through chaining.
- Portal targets open `/my`; internal targets open `/web` and Odoo resolves the target's accessible home view.
- The optional Ctrl+Shift+U shortcut opens the switcher. The configured reason is enforced server-side.
- Audit records are available under Settings > Technical > Impersonation Log to managers and auditors. Normal users have no access.

## Security and data protection

Switching does not read or set the target's password, API keys, TOTP secret, password hash, or existing authentication token. The module changes the server-side Odoo session UID and regenerates Odoo's session token. All switching endpoints are authenticated and validate Odoo's CSRF token. Manager authorization, target eligibility, company scope, allowlists, rate limits, and duration are checked on the server.

Audit rows reject ORM create/write/unlink from users; the module's private server methods create or close them, and the retention job uses a bounded SQL purge followed by a purge event. Session IDs are stored only as a SHA-256 digest, not in clear text. Request counts include requests during the active session; write counts include ORM create/write/unlink record operations. Detailed per-action payloads are not stored.

Impersonation exposes the target user's data and permits actions available to that user. Use it only in accordance with the organization's data-protection, audit, and employee-notice policies. The optional notification posts an internal note to the target user's partner; enable it only after reviewing local policy.

## Verification notes and known boundaries

- Security tests are in `tests/test_impersonation_security.py` and run with Odoo's test runner (`--test-enable --stop-after-init -i ma_login_as_user`).
- Maximum duration is enforced on each request and restored at the next request; the daily retention job also closes stale sessions after their configured limit (or the standard inactivity horizon for unlimited sessions).
- A session that expires before Odoo dispatches the add-on's request is reconciled by the retention job; immediate closure at the exact storage-expiry instant depends on Odoo's session store lifecycle.
- This initial release does not provide a detailed per-action payload journal, nor does it claim an end-to-end browser tour or cross-version support. It only counts ORM writes and HTTP requests.
- Install the module first on a test database, review all access groups and switching policy, and test notifications, proxy IP handling, multi-company access, and business-specific flows before production use.

## License

LGPL-3. See `LICENSE`.

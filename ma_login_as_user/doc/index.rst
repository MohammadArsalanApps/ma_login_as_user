Login as Any User
=================

Overview
--------

This on-premise Odoo 20.0 module (Community or Enterprise) enables a designated Impersonation Manager to
open an eligible user's session for support and testing. It keeps the target
user as the effective Odoo user so normal access rights and record rules apply.
The session is auditable and can be returned to the original manager without
the target's password.

Installation
------------

Copy the ``ma_login_as_user`` directory to an Odoo addons path, update the Apps
list, and install the module. The installation hook grants the built-in
administrator the manager role once and writes a server log entry. Configure
additional managers and auditors explicitly.

Configuration
-------------

Open Settings and find the Login as Any User settings panel. Choose the target
scope, portal and administrator eligibility, whether a reason is required,
the maximum duration, notification behavior, IP CIDRs, production lock, and
audit retention. The server-level ``ma_login_as_user_enabled = False`` option
in ``odoo.conf`` overrides the database setting and disables switching.

Usage
-----

Use the user-secret icon in the backend systray to search eligible users, or
open a user record and use ``Login as this user``. The user-list contextual
action supports one selected row. The target session displays a persistent
amber identity banner and elapsed timer; use ``Return to my account`` to restore
the original administrator session. Portal users are redirected to ``/my``;
internal users return to ``/web``.

Audit logs
----------

Managers and Impersonation Auditors can review read-only entries under
Settings > Technical > Impersonation Log. The list, detail form, and pivot
include administrator, target, company, start/end, status, reason, request and
write counts, source IP, user agent, session digest, and database name.

FAQ
---

Does this reset a password?
   No. The target's password and credentials are not read or changed.

Does it bypass the manager's two-factor authentication?
   No. The manager must already have a fully authenticated Odoo session. The
   module does not perform or disable MFA.

Can the target switch to another user?
   No. Switching is always authorized and audited as the original manager.

Troubleshooting
---------------

If the switcher is missing, confirm that the current administrator belongs to
the Impersonation Manager group, that the production lock and server kill switch
are off, and that the request IP matches the optional CIDR allowlist. If a
target is missing, check the configured company and group scope, active state,
administrator restriction, and portal restriction. For session errors, refresh
the page and review the audit entry and Odoo server log.

Data protection
---------------

Impersonation may expose personal or confidential information and permits
actions allowed to the target user. Use it only under the organization's
data-protection policy and retain audit logs for an appropriate period.

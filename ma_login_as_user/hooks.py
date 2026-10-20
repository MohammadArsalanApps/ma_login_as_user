import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Grant the installing administrator the manager role and record it."""
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    manager_group = env.ref(
        "ma_login_as_user.group_impersonation_manager", raise_if_not_found=False
    )
    if admin and manager_group and manager_group not in admin.groups_id:
        admin.write({"groups_id": [(4, manager_group.id)]})
        env["ir.logging"].sudo().create({
            "name": "Login as Any User",
            "type": "server",
            "dbname": env.cr.dbname,
            "level": "WARNING",
            "message": "Initial impersonation-manager role granted to the installing administrator.",
            "path": "ma_login_as_user",
            "func": "post_init_hook",
            "line": "0",
        })
        _logger.warning("Granted initial Login as Any User manager role to user %s", admin.id)

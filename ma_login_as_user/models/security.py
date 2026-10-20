import ipaddress

from odoo import SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import config


def module_enabled(env):
    """Return whether both the server kill switch and database lock permit use."""
    server_flag = config.get("ma_login_as_user_enabled", True)
    if isinstance(server_flag, str):
        server_flag = server_flag.strip().lower() not in {"0", "false", "no", "off"}
    locked = env["ir.config_parameter"].sudo().get_param(
        "ma_login_as_user.production_lock", "False"
    )
    return bool(server_flag) and locked.lower() not in {"1", "true", "yes", "on"}


def require_manager(user):
    if user.id == SUPERUSER_ID or not user.has_group(
        "ma_login_as_user.group_impersonation_manager"
    ):
        raise AccessError(_("You are not allowed to use this feature."))


def allowed_company_ids(user):
    return set(user.company_ids.ids)


def parse_ip_allowlist(env):
    raw = env["ir.config_parameter"].sudo().get_param(
        "ma_login_as_user.ip_allowlist", ""
    )
    networks = []
    for item in filter(None, (part.strip() for part in raw.split(","))):
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError as exc:
            raise UserError(_("The IP allowlist contains an invalid network.")) from exc
    return networks


def validate_ip(env, ip_address):
    networks = parse_ip_allowlist(env)
    if not networks:
        return
    try:
        address = ipaddress.ip_address(ip_address)
    except ValueError as exc:
        raise AccessError(_("You are not allowed to use this feature.")) from exc
    if not any(address in network for network in networks):
        raise AccessError(_("You are not allowed to use this feature."))


def validate_target(env, manager, target):
    """Enforce target eligibility without reading any credential fields."""
    if not module_enabled(env):
        raise AccessError(_("User switching is disabled by the system administrator."))
    require_manager(manager)
    if target.id in {manager.id, SUPERUSER_ID}:
        raise UserError(_("This account cannot be selected."))
    root = env.ref("base.user_root", raise_if_not_found=False)
    if root and target.id == root.id:
        raise UserError(_("This account cannot be selected."))
    if not target.active:
        raise UserError(_("This account cannot be selected."))
    params = env["ir.config_parameter"].sudo()
    if target.has_group("base.group_system") and params.get_param(
        "ma_login_as_user.allow_administrators", "False"
    ).lower() not in {"1", "true", "yes", "on"}:
        raise UserError(_("Administrator accounts are excluded by the current policy."))
    if target.share and params.get_param(
        "ma_login_as_user.allow_portal", "True"
    ).lower() in {"0", "false", "no", "off"}:
        raise UserError(_("Portal accounts are excluded by the current policy."))

    scope = params.get_param("ma_login_as_user.target_scope", "all")
    manager_companies = allowed_company_ids(manager)
    target_companies = set(target.company_ids.ids)
    if target.company_id:
        target_companies.add(target.company_id.id)
    if scope == "same_company" and not (manager_companies & target_companies):
        raise UserError(_("This account is outside the permitted company scope."))
    if scope == "groups":
        group_ids = params.get_param("ma_login_as_user.allowed_group_ids", "")
        allowed_ids = {int(value) for value in group_ids.split(",") if value.isdigit()}
        if not allowed_ids or not (allowed_ids & set(target.groups_id.ids)):
            raise UserError(_("This account is outside the permitted group scope."))
    if not (manager_companies & target_companies):
        raise UserError(_("This account is outside the permitted company scope."))

    reason_required = params.get_param(
        "ma_login_as_user.require_reason", "False"
    ).lower() in {"1", "true", "yes", "on"}
    return reason_required



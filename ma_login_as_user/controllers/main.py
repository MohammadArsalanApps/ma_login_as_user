import time
from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from ..models.security import module_enabled, require_manager, validate_ip, validate_target


class LoginAsUserController(http.Controller):
    """Authenticated, CSRF-checked JSON endpoints for session switching."""

    def _csrf(self, token):
        if not token or not request.validate_csrf(token):
            from werkzeug.exceptions import BadRequest
            raise BadRequest("Invalid request token.")

    def _manager(self):
        manager_id = request.session.get("ma_impersonator_uid") or request.session.uid
        manager = request.env["res.users"].sudo().browse(manager_id).exists()
        if not manager:
            raise AccessError(_("You are not allowed to use this feature."))
        require_manager(manager)
        if request.session.get("ma_impersonator_uid") and request.session.uid == manager.id:
            raise AccessError(_("You are not allowed to use this feature."))
        return manager

    def _enabled(self, manager):
        if not module_enabled(request.env):
            raise AccessError(_("User switching is currently disabled."))
        require_manager(manager)
        validate_ip(request.env, request.httprequest.remote_addr or "")

    def _user_payload(self, user, manager):
        is_internal = not user.share
        company = user.company_id
        return {
            "id": user.id,
            "name": user.name,
            "login": user.login,
            "company": company.name if company else "",
            "kind": "Internal" if is_internal else "Portal",
            "avatar": f"/web/image/res.users/{user.id}/avatar_128",
        }

    def _candidate_domain(self, manager, query):
        domain = [("active", "=", True), ("id", "!=", manager.id)]
        root = request.env.ref("base.user_root", raise_if_not_found=False)
        if root:
            domain.append(("id", "!=", root.id))
        if not request.env["ir.config_parameter"].sudo().get_param(
            "ma_login_as_user.allow_administrators", "False"
        ).lower() in {"1", "true", "yes", "on"}:
            domain.append(("groups_id", "not in", [request.env.ref("base.group_system").id]))
        if request.env["ir.config_parameter"].sudo().get_param(
            "ma_login_as_user.allow_portal", "True"
        ).lower() in {"0", "false", "no", "off"}:
            domain.append(("share", "=", False))
        manager_company_ids = manager.company_ids.ids
        domain.extend([("company_ids", "in", manager_company_ids)])
        if query:
            domain += ["|", "|", ("name", "ilike", query), ("login", "ilike", query), ("email", "ilike", query)]
        return domain

    @http.route("/ma_login_as/status", type="json", auth="user", methods=["POST"], csrf=False)
    def status(self, csrf_token=None):
        self._csrf(csrf_token)
        manager = self._manager()
        enabled = module_enabled(request.env) and manager.has_group(
            "ma_login_as_user.group_impersonation_manager"
        )
        impersonating = bool(request.session.get("ma_impersonator_uid"))
        params = request.env["ir.config_parameter"].sudo()
        payload = {
            "enabled": enabled,
            "impersonating": impersonating,
            "shortcut": params.get_param("ma_login_as_user.shortcut_enabled", "True").lower() not in {"0", "false", "no"},
            "requireReason": params.get_param("ma_login_as_user.require_reason", "False").lower() in {"1", "true", "yes", "on"},
        }
        if impersonating:
            target = request.env["res.users"].sudo().browse(request.session.uid).exists()
            payload.update({
                "target": {"name": target.name, "login": target.login} if target else {},
                "admin": {"name": manager.name, "login": manager.login},
                "started": request.session.get("ma_impersonation_started", 0),
                "maxDuration": int(params.get_param("ma_login_as_user.max_duration", "120")),
            })
        if enabled:
            prefs = request.env["ma.impersonation.preference"].sudo().search(
                [("owner_id", "=", manager.id)], order="last_used desc, id desc", limit=100
            )
            eligible = []
            for pref in prefs:
                target = pref.target_id
                try:
                    validate_target(request.env, manager, target)
                except (AccessError, UserError):
                    continue
                eligible.append((pref, target))
            payload["favorites"] = [
                self._user_payload(target, manager)
                for pref, target in eligible if pref.favorite
            ]
            payload["recents"] = [
                self._user_payload(target, manager)
                for pref, target in eligible if pref.last_used
            ][:5]
        return payload

    @http.route("/ma_login_as/search", type="json", auth="user", methods=["POST"], csrf=False)
    def search_users(self, query="", offset=0, csrf_token=None):
        self._csrf(csrf_token)
        manager = self._manager()
        self._enabled(manager)
        offset = max(0, min(int(offset or 0), 100000))
        query = (query or "").strip()[:100]
        users = request.env["res.users"].sudo().search(
            self._candidate_domain(manager, query), order="name, id", offset=offset, limit=50
        )
        allowed = []
        for user in users:
            try:
                validate_target(request.env, manager, user)
            except (AccessError, UserError):
                continue
            allowed.append(self._user_payload(user, manager))
        return {"users": allowed, "offset": offset, "hasMore": len(users) == 50}

    @http.route("/ma_login_as/favorite", type="json", auth="user", methods=["POST"], csrf=False)
    def favorite(self, target_id=None, favorite=False, csrf_token=None):
        self._csrf(csrf_token)
        manager = self._manager()
        self._enabled(manager)
        target = request.env["res.users"].sudo().browse(int(target_id or 0)).exists()
        if not target:
            raise UserError(_("This account cannot be selected."))
        validate_target(request.env, manager, target)
        Preference = request.env["ma.impersonation.preference"].sudo()
        pref = Preference.search([("owner_id", "=", manager.id), ("target_id", "=", target.id)], limit=1)
        if pref:
            pref.write({"favorite": bool(favorite)})
        else:
            Preference.create({"owner_id": manager.id, "target_id": target.id, "favorite": bool(favorite)})
        return {"ok": True}

    @http.route("/ma_login_as/switch", type="json", auth="user", methods=["POST"], csrf=False)
    def switch(self, target_id=None, reason="", csrf_token=None):
        self._csrf(csrf_token)
        manager = self._manager()
        self._enabled(manager)
        target = request.env["res.users"].sudo().browse(int(target_id or 0)).exists()
        if not target:
            raise UserError(_("This account cannot be selected."))
        reason_required = validate_target(request.env, manager, target)
        reason = (reason or "").strip()[:500]
        if reason_required and len(reason) < 5:
            raise UserError(_("Enter a reason of at least 5 characters."))

        request.env.cr.execute(
            "SELECT count(*) FROM ma_impersonation_log WHERE admin_id = %s AND start >= NOW() - INTERVAL '10 minutes'",
            [manager.id],
        )
        if request.env.cr.fetchone()[0] >= 30:
            raise UserError(_("Switch limit reached. Try again in a few minutes."))

        session = request.session
        prior_log = session.get("ma_impersonation_log_id")
        if prior_log:
            request.env["ma.impersonation.log"].sudo()._close_event(prior_log, "returned")
        else:
            session["ma_impersonator_uid"] = manager.id
            session["ma_impersonator_login"] = manager.login
            session["ma_impersonator_name"] = manager.name
            session["ma_impersonation_original_context"] = dict(session.context or manager.context_get())

        manager_companies = set(manager.company_ids.ids)
        permitted_companies = sorted(manager_companies & set(target.company_ids.ids))
        if not permitted_companies:
            raise UserError(_("This account is outside the permitted company scope."))
        default_company_id = target.company_id.id if target.company_id.id in permitted_companies else permitted_companies[0]
        context = dict(target.context_get())
        context["allowed_company_ids"] = permitted_companies
        context["company_id"] = default_company_id

        Log = request.env["ma.impersonation.log"].sudo()
        log = Log._create_event({
            "admin_id": manager.id,
            "target_id": target.id,
            "company_id": default_company_id,
            "start": fields.Datetime.now(),
            "status": "active",
            "reason": reason,
            "ip_address": (request.httprequest.remote_addr or "")[:64],
            "user_agent": (request.httprequest.user_agent.string or "")[:512],
            "session_hash": Log._session_hash(session.sid),
            "database_name": request.env.cr.dbname,
            "detail_enabled": request.env["ir.config_parameter"].sudo().get_param(
                "ma_login_as_user.detailed_actions", "False"
            ).lower() in {"1", "true", "yes", "on"},
        })

        Preference = request.env["ma.impersonation.preference"].sudo()
        pref = Preference.search([("owner_id", "=", manager.id), ("target_id", "=", target.id)], limit=1)
        if pref:
            pref.write({"last_used": fields.Datetime.now()})
        else:
            Preference.create({"owner_id": manager.id, "target_id": target.id, "last_used": fields.Datetime.now()})

        if request.env["ir.config_parameter"].sudo().get_param(
            "ma_login_as_user.notify_target", "False"
        ).lower() in {"1", "true", "yes", "on"}:
            target.partner_id.message_post(
                body=_("Your account was accessed by %(admin)s for: %(reason)s", admin=manager.name, reason=reason or _("Testing")),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

        session.uid = target.id
        session.login = target.login
        session.context = context
        session.session_token = target._compute_session_token(session.sid)
        session["ma_impersonation_log_id"] = log.id
        session["ma_impersonation_started"] = time.time()
        session.should_rotate = True
        request.update_env(user=target.id, context=context)
        return {"ok": True, "reload": True, "redirect": "/my" if target.share else "/web"}

    @http.route("/ma_login_as/return", type="json", auth="user", methods=["POST"], csrf=False)
    def return_to_admin(self, csrf_token=None):
        self._csrf(csrf_token)
        manager_id = request.session.get("ma_impersonator_uid")
        log_id = request.session.get("ma_impersonation_log_id")
        if not manager_id or not log_id:
            raise AccessError(_("There is no active switched session."))
        manager = request.env["res.users"].sudo().browse(manager_id).exists()
        if not manager or not manager.active or not manager.has_group(
            "ma_login_as_user.group_impersonation_manager"
        ):
            request.env["ma.impersonation.log"].sudo()._close_event(log_id, "forced")
            request.session.logout(keep_db=True)
            return {"ok": True, "reload": True, "loggedOut": True}
        request.env["ma.impersonation.log"].sudo()._close_event(log_id, "returned")
        context = request.session.get("ma_impersonation_original_context") or manager.context_get()
        request.session.uid = manager.id
        request.session.login = manager.login
        request.session.context = context
        request.session.session_token = manager._compute_session_token(request.session.sid)
        for key in ("ma_impersonator_uid", "ma_impersonator_login", "ma_impersonator_name",
                    "ma_impersonation_log_id", "ma_impersonation_started", "ma_impersonation_original_context"):
            request.session.pop(key, None)
        request.session.should_rotate = True
        request.update_env(user=manager.id, context=context)
        return {"ok": True, "reload": True}

    @http.route("/ma_login_as/logout_audit", type="json", auth="user", methods=["POST"], csrf=False)
    def logout_audit(self, csrf_token=None):
        self._csrf(csrf_token)
        log_id = request.session.get("ma_impersonation_log_id")
        if log_id:
            request.env["ma.impersonation.log"].sudo()._close_event(log_id, "logout")
        return {"ok": True}

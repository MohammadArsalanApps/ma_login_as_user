from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @staticmethod
    def _ma_end_response(message, redirect):
        from odoo.http import request
        if request.httprequest.mimetype == "application/json":
            return request.make_json_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": 403,
                    "message": message,
                    "data": {"name": "odoo.exceptions.AccessError", "message": message},
                },
            }, status=403)
        return request.redirect(redirect)

    @classmethod
    def _dispatch(cls, endpoint):
        from odoo.http import request
        from .security import module_enabled

        if request and request.session and request.session.get("ma_impersonator_uid"):
            manager_id = request.session.get("ma_impersonator_uid")
            log_id = request.session.get("ma_impersonation_log_id")
            admin = request.env["res.users"].sudo().browse(manager_id).exists()
            target_id = request.session.uid
            expired = False
            if admin and admin.active and admin.has_group("ma_login_as_user.group_impersonation_manager"):
                max_minutes = int(request.env["ir.config_parameter"].sudo().get_param(
                    "ma_login_as_user.max_duration", "120"
                ))
                started = request.session.get("ma_impersonation_started", 0)
                expired = bool(max_minutes and started and __import__("time").time() - started >= max_minutes * 60)
            if request.httprequest.path == "/web/session/destroy":
                request.env["ma.impersonation.log"].sudo()._close_event(log_id, "logout")
            elif not admin or not admin.active or not admin.has_group("ma_login_as_user.group_impersonation_manager"):
                request.env["ma.impersonation.log"].sudo()._close_event(log_id, "forced")
                request.session.logout(keep_db=True)
                return cls._ma_end_response(
                    "Your switched session ended because the manager account is no longer authorized.",
                    "/web/login",
                )
            elif not module_enabled(request.env):
                request.env["ma.impersonation.log"].sudo()._close_event(log_id, "forced")
                request.session.uid = admin.id
                request.session.login = admin.login
                request.session.context = dict(admin.context_get())
                request.session.session_token = admin._compute_session_token(request.session.sid)
                for key in ("ma_impersonator_uid", "ma_impersonator_login", "ma_impersonator_name",
                            "ma_impersonation_log_id", "ma_impersonation_started", "ma_impersonation_original_context"):
                    request.session.pop(key, None)
                request.session.should_rotate = True
                request.update_env(user=admin.id)
                return cls._ma_end_response(
                    "User switching was disabled. Your administrator account has been restored.",
                    "/web",
                )
            elif expired:
                request.env["ma.impersonation.log"].sudo()._close_event(log_id, "expired")
                request.session.uid = admin.id
                request.session.login = admin.login
                request.session.context = dict(admin.context_get())
                request.session.session_token = admin._compute_session_token(request.session.sid)
                request.session.should_rotate = True
                for key in ("ma_impersonator_uid", "ma_impersonator_login", "ma_impersonator_name",
                            "ma_impersonation_log_id", "ma_impersonation_started", "ma_impersonation_original_context"):
                    request.session.pop(key, None)
                request.update_env(user=admin.id)
                return cls._ma_end_response(
                    "The switched session expired. Your administrator account has been restored.",
                    "/web",
                )
            request.env.cr.execute(
                "UPDATE ma_impersonation_log SET request_count = request_count + 1 WHERE id = %s AND status = 'active'",
                [int(log_id)],
            )
            request.update_context(**{"ma_impersonation_log_id": int(log_id)})
        return super()._dispatch(endpoint)

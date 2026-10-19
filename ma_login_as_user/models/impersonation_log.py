import hashlib
import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)
_INTERNAL_CONTEXT_KEY = "_ma_login_as_user_internal"


class ImpersonationLog(models.Model):
    _name = "ma.impersonation.log"
    _description = "User Impersonation Audit Log"
    _order = "start desc, id desc"
    _rec_name = "target_id"

    admin_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict", index=True)
    target_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict", index=True)
    company_id = fields.Many2one("res.company", readonly=True, ondelete="restrict", index=True)
    start = fields.Datetime(required=True, readonly=True, default=fields.Datetime.now, index=True)
    end = fields.Datetime(readonly=True)
    duration_seconds = fields.Integer(readonly=True)
    status = fields.Selection([
        ("active", "Active"), ("returned", "Returned"), ("expired", "Expired"),
        ("logout", "Logout"), ("forced", "Forced"), ("purge", "Retention purge"),
    ], required=True, readonly=True, default="active", index=True)
    reason = fields.Char(readonly=True, size=500)
    ip_address = fields.Char(readonly=True, size=64)
    user_agent = fields.Char(readonly=True, size=512)
    session_hash = fields.Char(readonly=True, size=64, index=True)
    request_count = fields.Integer(readonly=True, default=0)
    write_count = fields.Integer(readonly=True, default=0)
    database_name = fields.Char(readonly=True, required=True)
    detail_enabled = fields.Boolean(readonly=True, default=False)
    action_ids = fields.One2many("ma.impersonation.action", "log_id", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.su and self.env.context.get(_INTERNAL_CONTEXT_KEY)):
            raise AccessError(_("Audit records can only be created by the audit service."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Audit records are immutable."))

    def unlink(self):
        raise AccessError(_("Audit records are immutable."))

    @api.model
    def _create_event(self, vals):
        """Private service entry point used only by trusted module code."""
        return self.sudo().with_context(**{_INTERNAL_CONTEXT_KEY: True}).create(vals)

    @api.model
    def _close_event(self, log_id, status):
        if status not in {"returned", "expired", "logout", "forced"}:
            raise ValueError("Invalid audit close status")
        self.env.cr.execute(
            """UPDATE ma_impersonation_log
                  SET status = %s, "end" = NOW(),
                      duration_seconds = GREATEST(0, EXTRACT(EPOCH FROM (NOW() - start))::integer)
                WHERE id = %s AND status = 'active'""",
            [status, int(log_id)],
        )

    @api.model
    def _session_hash(self, sid):
        salt = self.env["ir.config_parameter"].sudo().get_param("database.uuid", "")
        return hashlib.sha256(f"{salt}:{sid}".encode()).hexdigest()

    @api.model
    def _purge_expired(self):
        retention = int(self.env["ir.config_parameter"].sudo().get_param(
            "ma_login_as_user.retention_days", "365"
        ))
        retention = max(1, min(retention, 3650))
        cutoff = fields.Datetime.to_string(datetime.utcnow() - timedelta(days=retention))
        max_minutes = int(self.env["ir.config_parameter"].sudo().get_param(
            "ma_login_as_user.max_duration", "120"
        ))
        if max_minutes:
            self.env.cr.execute(
                """UPDATE ma_impersonation_log
                      SET status = 'expired', "end" = NOW(),
                          duration_seconds = GREATEST(0, EXTRACT(EPOCH FROM (NOW() - start))::integer)
                    WHERE status = 'active' AND start < NOW() - (%s * INTERVAL '1 minute')""",
                [max_minutes],
            )
        else:
            max_idle = int(self.env["ir.config_parameter"].sudo().get_param(
                "sessions.max_inactivity_seconds", "604800"
            ))
            self.env.cr.execute(
                """UPDATE ma_impersonation_log
                      SET status = 'expired', "end" = NOW(),
                          duration_seconds = GREATEST(0, EXTRACT(EPOCH FROM (NOW() - start))::integer)
                    WHERE status = 'active' AND start < NOW() - (%s * INTERVAL '1 second')""",
                [max_idle],
            )
        self.env.cr.execute(
            'SELECT count(*) FROM ma_impersonation_log WHERE "end" IS NOT NULL AND "end" < %s',
            [cutoff],
        )
        count = self.env.cr.fetchone()[0]
        if count:
            self.env.cr.execute(
                'DELETE FROM ma_impersonation_log WHERE "end" IS NOT NULL AND "end" < %s',
                [cutoff],
            )
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin:
            self._create_event({
                "admin_id": admin.id,
                "target_id": admin.id,
                "company_id": admin.company_id.id,
                "status": "purge",
                "reason": _("Retention purge removed %s audit entries.", count),
                "database_name": self.env.cr.dbname,
                "start": fields.Datetime.now(),
                "end": fields.Datetime.now(),
                "duration_seconds": 0,
            })
            _logger.warning("Impersonation log retention purge removed %s records", count)

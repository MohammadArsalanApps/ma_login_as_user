from odoo import api, fields, models
from odoo.exceptions import AccessError

from .impersonation_log import _INTERNAL_CONTEXT_KEY


class ImpersonationAction(models.Model):
    _name = "ma.impersonation.action"
    _description = "Impersonated ORM action metadata"
    _order = "event_time desc, id desc"

    log_id = fields.Many2one("ma.impersonation.log", required=True, readonly=True, ondelete="cascade", index=True)
    event_time = fields.Datetime(required=True, readonly=True, default=fields.Datetime.now, index=True)
    operation = fields.Selection([("create", "Create"), ("write", "Update"), ("unlink", "Delete")], required=True, readonly=True)
    model_name = fields.Char(required=True, readonly=True, size=128)
    record_count = fields.Integer(required=True, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not (self.env.su and self.env.context.get(_INTERNAL_CONTEXT_KEY)):
            raise AccessError("Action audit records can only be created by the audit service.")
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError("Action audit records are immutable.")

    def unlink(self):
        raise AccessError("Action audit records are immutable.")

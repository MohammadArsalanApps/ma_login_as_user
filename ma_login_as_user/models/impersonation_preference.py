from odoo import fields, models


class ImpersonationPreference(models.Model):
    _name = "ma.impersonation.preference"
    _description = "Per-administrator impersonation preferences"
    _order = "last_used desc, id desc"
    _sql_constraints = [
        (
            "owner_target_unique",
            "UNIQUE(owner_id, target_id)",
            "Preference already exists.",
        ),
    ]

    owner_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    target_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    favorite = fields.Boolean(default=False, index=True)
    last_used = fields.Datetime()

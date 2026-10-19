from odoo import api, fields, models
from odoo.exceptions import AccessError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ma_login_allow_administrators = fields.Boolean(
        string="Allow switching into Settings administrators",
        config_parameter="ma_login_as_user.allow_administrators",
    )
    ma_login_allow_portal = fields.Boolean(
        string="Allow switching into portal users", default=True,
        config_parameter="ma_login_as_user.allow_portal",
    )
    ma_login_target_scope = fields.Selection([
        ("all", "All users in my allowed companies"),
        ("same_company", "Users in a shared company"),
        ("groups", "Users in selected groups"),
    ], default="all", config_parameter="ma_login_as_user.target_scope")
    ma_login_allowed_group_ids = fields.Many2many(
        "res.groups", string="Allowed target groups", compute="_compute_ma_login_groups",
        inverse="_inverse_ma_login_groups", groups="base.group_system",
    )
    ma_login_require_reason = fields.Boolean(
        string="Require a reason", config_parameter="ma_login_as_user.require_reason",
    )
    ma_login_max_duration = fields.Integer(
        string="Maximum session duration (minutes; 0 = unlimited)", default=120,
        config_parameter="ma_login_as_user.max_duration",
    )
    ma_login_notify_target = fields.Boolean(
        string="Notify the target user", config_parameter="ma_login_as_user.notify_target",
    )
    ma_login_production_lock = fields.Boolean(
        string="Production lock", config_parameter="ma_login_as_user.production_lock",
    )
    ma_login_ip_allowlist = fields.Char(
        string="IP allowlist (CIDR, comma-separated)",
        config_parameter="ma_login_as_user.ip_allowlist",
    )
    ma_login_detailed_actions = fields.Boolean(
        string="Record detailed action metadata", config_parameter="ma_login_as_user.detailed_actions",
    )
    ma_login_retention_days = fields.Integer(
        string="Audit retention (days)", default=365,
        config_parameter="ma_login_as_user.retention_days",
    )
    ma_login_shortcut_enabled = fields.Boolean(
        string="Enable Ctrl+Shift+U shortcut", default=True,
        config_parameter="ma_login_as_user.shortcut_enabled",
    )

    @api.depends_context("uid")
    def _compute_ma_login_groups(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "ma_login_as_user.allowed_group_ids", ""
        )
        ids = [int(value) for value in param.split(",") if value.isdigit()]
        groups = self.env["res.groups"].browse(ids).exists()
        for record in self:
            record.ma_login_allowed_group_ids = groups

    def _inverse_ma_login_groups(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError("Only Settings administrators may change impersonation policy.")
        ids = ",".join(str(value) for value in self.ma_login_allowed_group_ids.ids)
        self.env["ir.config_parameter"].sudo().set_param(
            "ma_login_as_user.allowed_group_ids", ids
        )

    def set_values(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError("Only Settings administrators may change impersonation policy.")
        self.ma_login_max_duration = max(0, min(self.ma_login_max_duration, 10080))
        self.ma_login_retention_days = max(1, min(self.ma_login_retention_days, 3650))
        return super().set_values()

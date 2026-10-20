from odoo import api, models


class IrConfigParameter(models.Model):
    """Keep the module's string-based settings API on Odoo 20."""

    _inherit = "ir.config_parameter"

    @api.model
    def get_param(self, key, default=False):
        return self.get_str(key, default)

    @api.model
    def set_param(self, key, value):
        return self.set_str(key, value)

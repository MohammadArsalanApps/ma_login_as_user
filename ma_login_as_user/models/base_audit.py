from odoo import api, models


class BaseAudit(models.AbstractModel):
    _inherit = "base"

    def _ma_count_writes(self, count, operation):
        session = self.env.context.get("ma_impersonation_log_id")
        if session and self._name not in {"ma.impersonation.log", "ma.impersonation.action"}:
            self.env.cr.execute(
                "UPDATE ma_impersonation_log SET write_count = write_count + %s WHERE id = %s AND status = 'active' RETURNING detail_enabled",
                [count, int(session)],
            )
            row = self.env.cr.fetchone()
            if row and row[0]:
                self.env.cr.execute(
                    """INSERT INTO ma_impersonation_action
                           (log_id, event_time, operation, model_name, record_count, create_uid, create_date, write_uid, write_date)
                         VALUES (%s, NOW(), %s, %s, %s, %s, NOW(), %s, NOW())""",
                    [int(session), operation, self._name[:128], count, self.env.uid, self.env.uid],
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._ma_count_writes(len(records), "create")
        return records

    def write(self, vals):
        result = super().write(vals)
        self._ma_count_writes(len(self), "write")
        return result

    def unlink(self):
        count = len(self)
        result = super().unlink()
        self._ma_count_writes(count, "unlink")
        return result

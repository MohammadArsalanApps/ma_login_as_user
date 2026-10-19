from odoo import _, models
from odoo.exceptions import AccessError

from .security import require_manager


class ResUsers(models.Model):
    _inherit = "res.users"

    def write(self, vals):
        manager_group = self.env.ref("ma_login_as_user.group_impersonation_manager", raise_if_not_found=False)
        auditor_group = self.env.ref("ma_login_as_user.group_impersonation_auditor", raise_if_not_found=False)
        protected_groups = {group.id for group in (manager_group, auditor_group) if group}
        if "group_ids" in vals and not self.env.su and not self.env.user.has_group("base.group_system"):
            commands = vals["group_ids"]
            protected_member = any(protected_groups & set(user.group_ids.ids) for user in self)
            changed_protected = any(
                isinstance(command, (tuple, list))
                and len(command) > 1
                and (
                    (command[0] == 6 and bool(set(command[2]) & protected_groups))
                    or (command[0] in (3, 4) and command[1] in protected_groups)
                    or (command[0] == 5 and protected_member)
                )
                for command in commands
            )
            if protected_member or changed_protected:
                raise AccessError(_("Only Settings administrators may assign impersonation roles."))
        return super().write(vals)

    def action_ma_login_as(self):
        if len(self) != 1:
            raise AccessError(_("Select one user to continue."))
        require_manager(self.env.user)
        return {
            "type": "ir.actions.client",
            "tag": "ma_login_as_user.open_switcher",
            "params": {"targetId": self.id},
        }

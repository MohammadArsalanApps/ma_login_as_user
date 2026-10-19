from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..models.security import module_enabled, validate_target


@tagged("post_install", "-at_install")
class TestImpersonationSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager_group = cls.env.ref("ma_login_as_user.group_impersonation_manager")
        cls.internal_group = cls.env.ref("base.group_user")
        cls.company = cls.env.company
        cls.manager = cls.env["res.users"].create({
            "name": "Demo Audit Manager",
            "login": "demo.audit.manager",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, [cls.company.id])],
            "group_ids": [(6, 0, [cls.internal_group.id, cls.manager_group.id])],
        })
        cls.target = cls.env["res.users"].create({
            "name": "Demo Target User",
            "login": "demo.target.user",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, [cls.company.id])],
            "group_ids": [(6, 0, [cls.internal_group.id])],
        })

    def test_self_and_root_are_rejected(self):
        with self.assertRaises(UserError):
            validate_target(self.env, self.manager, self.manager)
        root = self.env.ref("base.user_root")
        with self.assertRaises(UserError):
            validate_target(self.env, self.manager, root)

    def test_inactive_target_is_rejected(self):
        self.target.active = False
        with self.assertRaises(UserError):
            validate_target(self.env, self.manager, self.target)

    def test_reason_policy_is_server_enforced(self):
        self.env["ir.config_parameter"].sudo().set_param("ma_login_as_user.require_reason", "True")
        self.assertTrue(validate_target(self.env, self.manager, self.target))

    def test_production_lock_blocks_switching(self):
        self.env["ir.config_parameter"].sudo().set_param("ma_login_as_user.production_lock", "True")
        self.assertFalse(module_enabled(self.env))

    def test_audit_rows_are_immutable(self):
        log = self.env["ma.impersonation.log"]._create_event({
            "admin_id": self.manager.id,
            "target_id": self.target.id,
            "company_id": self.company.id,
            "database_name": self.env.cr.dbname,
            "reason": "Automated security test",
        })
        with self.assertRaises(AccessError):
            log.write({"reason": "tampered"})
        with self.assertRaises(AccessError):
            log.unlink()

    def test_public_create_is_denied(self):
        log_model = self.env["ma.impersonation.log"].with_user(self.target)
        with self.assertRaises(AccessError):
            log_model.create({
                "admin_id": self.manager.id,
                "target_id": self.target.id,
                "database_name": self.env.cr.dbname,
            })

    def test_retention_job_runs(self):
        self.env["ma.impersonation.log"]._purge_expired()

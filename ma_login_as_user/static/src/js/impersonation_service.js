import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { reactive } from "@odoo/owl";

const service = {
    dependencies: ["notification"],
    start(env, { notification }) {
        const state = reactive({
            enabled: false,
            impersonating: false,
            target: null,
            admin: null,
            started: 0,
            maxDuration: 0,
            requireReason: false,
            shortcut: true,
            favorites: [],
            recents: [],
            error: "",
        });

        async function call(route, params = {}) {
            return rpc(route, { csrf_token: odoo.csrf_token, ...params });
        }

        async function refresh() {
            try {
                const result = await call("/ma_login_as/status");
                Object.assign(state, result, { error: "" });
                return result;
            } catch (error) {
                const message = error?.data?.message || error?.message || "";
                if (message.toLowerCase().includes("expired")) {
                    notification.add("The switched session ended. Your administrator account has been restored.", { type: "warning" });
                    Object.assign(state, { enabled: true, impersonating: false, target: null, admin: null });
                } else {
                    Object.assign(state, { enabled: false, impersonating: false });
                }
                return null;
            }
        }

        async function switchUser(targetId, reason = "") {
            state.error = "";
            try {
                const result = await call("/ma_login_as/switch", { target_id: targetId, reason });
                window.location.assign(result.redirect || "/web");
            } catch (error) {
                state.error = error?.data?.message || error?.message || "Unable to switch user.";
                throw error;
            }
        }

        async function returnToAdmin() {
            state.error = "";
            try {
                await call("/ma_login_as/return");
                window.location.reload();
            } catch (error) {
                state.error = error?.data?.message || error?.message || "Unable to return to your account.";
                throw error;
            }
        }

        const ready = refresh();
        const timer = window.setInterval(refresh, 15000);
        window.addEventListener("pagehide", () => window.clearInterval(timer), { once: true });

        return {
            state,
            ready,
            refresh,
            async search(query, offset = 0) {
                return call("/ma_login_as/search", { query, offset });
            },
            async favorite(user, favorite) {
                await call("/ma_login_as/favorite", { target_id: user.id, favorite });
                await refresh();
            },
            switchUser,
            returnToAdmin,
            async logoutAudit() {
                return call("/ma_login_as/logout_audit");
            },
        };
    },
};

registry.category("services").add("ma_login_as_user", service);

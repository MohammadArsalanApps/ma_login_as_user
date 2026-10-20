/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";

export class ImpersonationBanner extends Component {
    static template = "ma_login_as_user.Banner";
    static props = {};

    setup() {
        this.impersonation = useService("ma_login_as_user");
        this.state = useState({ initialized: false, seconds: 0 });
        this.originalTitle = document.title;
        this.timer = window.setInterval(() => {
            const data = this.impersonation.state;
            if (data.impersonating) {
                this.state.seconds = Math.max(0, Math.floor(Date.now() / 1000 - data.started));
                const prefix = `[AS ${data.target?.name || "User"}] `;
                if (!document.title.startsWith(prefix)) {
                    this.originalTitle = document.title.replace(/^\[AS [^\]]+\] /, "");
                    document.title = prefix + this.originalTitle;
                }
            } else if (document.title.startsWith("[AS ")) {
                document.title = this.originalTitle;
            }
        }, 1000);
        onMounted(async () => {
            await this.impersonation.ready;
            this.state.initialized = true;
        });
        onWillUnmount(() => {
            window.clearInterval(this.timer);
            if (document.title.startsWith("[AS ")) document.title = this.originalTitle;
        });
    }

    get data() {
        return this.impersonation.state;
    }

    get elapsed() {
        const mins = Math.floor(this.state.seconds / 60).toString().padStart(2, "0");
        const secs = (this.state.seconds % 60).toString().padStart(2, "0");
        const hours = Math.floor(this.state.seconds / 3600);
        return `${hours ? `${hours}:` : ""}${mins}:${secs}`;
    }

    async returnToAdmin() {
        try {
            await this.impersonation.returnToAdmin();
        } catch {
            // The service keeps the error available to the user interface.
        }
    }
}

patch(WebClient, {
    components: { ...WebClient.components, ImpersonationBanner },
});

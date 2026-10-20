/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ImpersonationSwitcher extends Component {
    static template = "ma_login_as_user.Switcher";
    static props = {};

    setup() {
        this.impersonation = useService("ma_login_as_user");
        this.state = useState({ initialized: false, open: false, query: "", results: [], offset: 0, hasMore: false, loading: false, activeIndex: 0, pending: null, reason: "" });
        this.searchRef = useRef("search");
        this.searchTimer = null;
        this.onShortcut = this.onShortcut.bind(this);
        onMounted(async () => {
            await this.impersonation.ready;
            this.state.initialized = true;
            window.addEventListener("keydown", this.onShortcut);
        });
        onWillUnmount(() => {
            window.removeEventListener("keydown", this.onShortcut);
            window.clearTimeout(this.searchTimer);
        });
    }

    get serviceState() {
        return this.impersonation.state;
    }

    isFavorite(user) {
        return this.serviceState.favorites.some((item) => item.id === user.id);
    }

    onShortcut(event) {
        if (this.serviceState.shortcut && event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "u") {
            event.preventDefault();
            this.toggle();
        }
    }

    async toggle(force = null) {
        this.state.open = force === null ? !this.state.open : force;
        if (this.state.open) {
            this.state.query = "";
            this.state.pending = null;
            this.state.activeIndex = 0;
            await this.loadSearch();
            this.searchRef.el?.focus();
        }
    }

    onSearch(event) {
        this.state.query = event.target.value;
        this.state.offset = 0;
        this.state.activeIndex = 0;
        window.clearTimeout(this.searchTimer);
        this.searchTimer = window.setTimeout(() => this.loadSearch(), 250);
    }

    async loadSearch(append = false) {
        this.state.loading = true;
        this.serviceState.error = "";
        try {
            const result = await this.impersonation.search(this.state.query, append ? this.state.offset : 0);
            this.state.results = append ? [...this.state.results, ...result.users] : result.users;
            this.state.offset = this.state.results.length;
            this.state.hasMore = result.hasMore;
        } catch (error) {
            this.serviceState.error = error?.data?.message || error?.message || "Unable to load users.";
        } finally {
            this.state.loading = false;
        }
    }

    async toggleFavorite(user, event) {
        event.stopPropagation();
        const current = this.serviceState.favorites.some((item) => item.id === user.id);
        try {
            await this.impersonation.favorite(user, !current);
        } catch (error) {
            this.serviceState.error = error?.data?.message || "Unable to update favorites.";
        }
    }

    async selectUser(user) {
        if (this.serviceState.requireReason) {
            this.state.pending = user;
            this.state.reason = "";
            return;
        }
        await this.runSwitch(user, "");
    }

    async runSwitch(user, reason) {
        try {
            await this.impersonation.switchUser(user.id, reason);
        } catch {
            this.state.open = true;
        }
    }

    async confirmSwitch() {
        if (this.state.reason.trim().length < 5) {
            this.serviceState.error = "Enter a reason of at least 5 characters.";
            return;
        }
        await this.runSwitch(this.state.pending, this.state.reason.trim());
    }

    onKeydown(event) {
        const users = this.state.results;
        if (event.key === "Escape") {
            if (this.state.pending) this.state.pending = null;
            else this.toggle(false);
        } else if (event.key === "ArrowDown" && users.length) {
            event.preventDefault();
            this.state.activeIndex = (this.state.activeIndex + 1) % users.length;
        } else if (event.key === "ArrowUp" && users.length) {
            event.preventDefault();
            this.state.activeIndex = (this.state.activeIndex + users.length - 1) % users.length;
        } else if (event.key === "Enter" && users[this.state.activeIndex]) {
            event.preventDefault();
            this.selectUser(users[this.state.activeIndex]);
        }
    }
}

export class OpenSwitcherAction extends Component {
    static template = "ma_login_as_user.OpenSwitcherAction";
    static props = { action: { type: Object }, actionId: { type: Number, optional: true }, className: { type: String, optional: true } };

    setup() {
        this.impersonation = useService("ma_login_as_user");
        onMounted(async () => {
            const targetId = this.props.action?.params?.targetId;
            if (targetId) {
                try {
                    let reason = "";
                    if (this.impersonation.state.requireReason) {
                        reason = window.prompt("Enter the reason for switching (minimum 5 characters):") || "";
                        if (reason.trim().length < 5) return;
                    }
                    await this.impersonation.switchUser(targetId, reason);
                } catch (error) {
                    this.impersonation.state.error = error?.data?.message || error?.message || "Unable to switch user.";
                }
            }
        });
    }
}

registry.category("systray").add("ma_login_as_user.switcher", { Component: ImpersonationSwitcher }, { sequence: 30 });
registry.category("actions").add("ma_login_as_user.open_switcher", OpenSwitcherAction);

// Copyright (c) 2024, Hybrowlabs Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("AWS Settings", {
    refresh: function (frm) {
        if (frm.doc.enable_aws && frm.doc.enable_s3) {
            frm.add_custom_button(
                __("Test S3 Connection"),
                function () {
                    frappe.call({
                        method: "aws_integration.api.s3.test_s3_connection",
                        freeze: true,
                        freeze_message: __("Testing S3 Connection..."),
                        callback: function (r) {
                            if (r.message && r.message.success) {
                                frappe.msgprint({
                                    title: __("Success"),
                                    indicator: "green",
                                    message: r.message.message,
                                });
                            } else {
                                frappe.msgprint({
                                    title: __("Failed"),
                                    indicator: "red",
                                    message: r.message
                                        ? r.message.message
                                        : __("Connection failed"),
                                });
                            }
                        },
                    });
                },
                __("S3")
            );

            frm.add_custom_button(
                __("Migrate All Files to S3"),
                function () {
                    frappe.confirm(
                        __(
                            "This will upload all local files to S3. This may take a while. Continue?"
                        ),
                        function () {
                            frappe.call({
                                method: "aws_integration.api.s3.migrate_files_to_s3",
                                freeze: true,
                                freeze_message: __(
                                    "Starting file migration..."
                                ),
                                callback: function (r) {
                                    if (r.message) {
                                        frappe.msgprint(r.message);
                                    }
                                },
                                error: function () {
                                    frappe.msgprint({
                                        title: __("Error"),
                                        indicator: "red",
                                        message: __("Failed to start file migration."),
                                    });
                                },
                            });
                        }
                    );
                },
                __("S3")
            );

            frm.add_custom_button(
                __("S3 Status"),
                function () {
                    frappe.call({
                        method: "aws_integration.api.s3.get_s3_status",
                        freeze: true,
                        freeze_message: __("Fetching S3 status..."),
                        callback: function (r) {
                            if (!r.message) return;
                            let d = r.message;
                            let fmt_size = function (bytes) {
                                if (!bytes) return "0 B";
                                let units = ["B", "KB", "MB", "GB", "TB"];
                                let i = Math.floor(Math.log(bytes) / Math.log(1024));
                                return (bytes / Math.pow(1024, i)).toFixed(1) + " " + units[i];
                            };
                            let pct = d.total_files
                                ? ((d.on_s3 / d.total_files) * 100).toFixed(1)
                                : 0;

                            let html = `
                                <div class="s3-status-grid" style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                                    <div class="s3-stat" style="padding:12px; border-radius:8px; background:var(--bg-light-gray);">
                                        <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">${__("On S3")}</div>
                                        <div style="font-size:22px; font-weight:600; color:var(--text-color);">${d.on_s3}</div>
                                        <div style="font-size:12px; color:var(--text-muted);">${fmt_size(d.s3_size)}</div>
                                    </div>
                                    <div class="s3-stat" style="padding:12px; border-radius:8px; background:var(--bg-light-gray);">
                                        <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">${__("Pending Upload")}</div>
                                        <div style="font-size:22px; font-weight:600; color:${d.pending ? 'var(--orange-500)' : 'var(--text-color)'};">${d.pending}</div>
                                        <div style="font-size:12px; color:var(--text-muted);">${fmt_size(d.pending_size)}</div>
                                    </div>
                                    <div class="s3-stat" style="padding:12px; border-radius:8px; background:var(--bg-light-gray);">
                                        <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">${__("Exempt Files")}</div>
                                        <div style="font-size:22px; font-weight:600; color:var(--text-color);">${d.exempt}</div>
                                    </div>
                                    <div class="s3-stat" style="padding:12px; border-radius:8px; background:var(--bg-light-gray);">
                                        <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase;">${__("Total Files")}</div>
                                        <div style="font-size:22px; font-weight:600; color:var(--text-color);">${d.total_files}</div>
                                    </div>
                                </div>
                                <div style="margin-top:16px;">
                                    <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                                        <span style="font-size:12px; color:var(--text-muted);">${__("S3 Migration Progress")}</span>
                                        <span style="font-size:12px; font-weight:600;">${pct}%</span>
                                    </div>
                                    <div style="height:8px; background:var(--bg-light-gray); border-radius:4px; overflow:hidden;">
                                        <div style="height:100%; width:${pct}%; background:var(--primary); border-radius:4px; transition:width 0.3s;"></div>
                                    </div>
                                </div>
                                <div style="margin-top:12px; font-size:12px; color:var(--text-muted);">
                                    ${d.last_uploaded_at
                                        ? __("Last upload: {0}", [frappe.datetime.prettyDate(d.last_uploaded_at)])
                                        : __("No files uploaded yet")}
                                    ${d.recent_errors
                                        ? ' &middot; <span style="color:var(--red-500);">' + __("{0} errors in last 7 days", [d.recent_errors]) + '</span>'
                                        : ''}
                                </div>
                            `;

                            frappe.msgprint({
                                title: __("S3 Storage Status"),
                                message: html,
                                wide: true,
                                indicator: d.pending ? "orange" : "green",
                            });
                        },
                    });
                },
                __("S3")
            );

            frm.add_custom_button(
                __("Clean Up Local Files"),
                function () {
                    frappe.confirm(
                        __(
                            "This will delete local copies of files already uploaded to S3. This cannot be undone. Continue?"
                        ),
                        function () {
                            frappe.call({
                                method: "aws_integration.api.s3.cleanup_local_s3_files",
                                freeze: true,
                                freeze_message: __("Starting local cleanup..."),
                                callback: function (r) {
                                    if (r.message) {
                                        frappe.msgprint(r.message);
                                    }
                                },
                                error: function () {
                                    frappe.msgprint({
                                        title: __("Error"),
                                        indicator: "red",
                                        message: __("Failed to start local cleanup."),
                                    });
                                },
                            });
                        }
                    );
                },
                __("S3")
            );

        }

        if (frm.doc.enable_s3_backups) {
            frm.add_custom_button(
                __("Take Backup Now"),
                function () {
                    frappe.call({
                        method: "aws_integration.s3.backup.take_s3_backup",
                        freeze: true,
                        freeze_message: __("Queuing S3 Backup..."),
                        callback: function (r) {
                            if (r.message && r.message.log_name) {
                                frappe.msgprint({
                                    title: __("Backup Queued"),
                                    indicator: "blue",
                                    message: __("Backup job {0} has been queued. Track progress below.", [r.message.log_name]),
                                });
                            }
                        },
                        error: function () {
                            frappe.msgprint({
                                title: __("Error"),
                                indicator: "red",
                                message: __("Failed to start S3 backup."),
                            });
                        },
                    });
                },
                __("S3")
            );

            frm.add_custom_button(
                __("Backup Logs"),
                function () {
                    frappe.set_route("List", "S3 Backup Log");
                },
                __("S3")
            );
        }

        if (frm.doc.enable_aws && frm.doc.enable_s3) {
            // Listen for migration progress updates from the background job.
            // Use .off() first to prevent duplicate listeners on form refresh.
            frappe.realtime.off("s3_migration_progress");
            frappe.realtime.on("s3_migration_progress", function (data) {
                frappe.show_progress(
                    __("S3 Migration"),
                    data.uploaded + data.failed,
                    data.total,
                    __("{0} uploaded, {1} failed", [data.uploaded, data.failed])
                );
            });

            frappe.realtime.off("s3_migration_complete");
            frappe.realtime.on("s3_migration_complete", function (data) {
                frappe.hide_progress();
                frappe.msgprint({
                    title: __("S3 Migration Complete"),
                    indicator: data.failed ? "orange" : "green",
                    message: __("{0} files uploaded, {1} failed", [data.uploaded, data.failed]),
                });
            });

            frappe.realtime.off("s3_cleanup_progress");
            frappe.realtime.on("s3_cleanup_progress", function (data) {
                frappe.show_progress(
                    __("S3 Local Cleanup"),
                    data.deleted + data.missing + data.skipped,
                    data.total,
                    __("{0} deleted, {1} already gone", [data.deleted, data.missing])
                );
            });

            frappe.realtime.off("s3_cleanup_complete");
            frappe.realtime.on("s3_cleanup_complete", function (data) {
                frappe.hide_progress();
                frappe.msgprint({
                    title: __("S3 Local Cleanup Complete"),
                    indicator: data.skipped ? "orange" : "green",
                    message: __("{0} local files deleted, {1} already removed, {2} skipped", [
                        data.deleted, data.missing, data.skipped
                    ]),
                });
            });

            frappe.realtime.off("s3_backup_progress");
            frappe.realtime.on("s3_backup_progress", function (data) {
                if (data.status === "generating") {
                    frappe.show_progress(
                        __("S3 Backup"),
                        33, 100,
                        __("Generating backup files...")
                    );
                } else if (data.status === "uploading") {
                    frappe.show_progress(
                        __("S3 Backup"),
                        66, 100,
                        __("Uploading to S3...")
                    );
                } else if (data.status === "success") {
                    frappe.hide_progress();
                    let safe_name = frappe.utils.xss_sanitise(data.log_name || "");
                    frappe.msgprint({
                        title: __("Backup Complete"),
                        indicator: "green",
                        message: __("S3 backup completed successfully. View {0}.", [
                            '<a href="/app/s3-backup-log/' + encodeURIComponent(safe_name) + '">' + safe_name + '</a>'
                        ]),
                    });
                } else if (data.status === "failed") {
                    frappe.hide_progress();
                    let safe_fail_name = frappe.utils.xss_sanitise(data.log_name || "");
                    frappe.msgprint({
                        title: __("Backup Failed"),
                        indicator: "red",
                        message: __("S3 backup failed. Check {0} for details.", [
                            '<a href="/app/s3-backup-log/' + encodeURIComponent(safe_fail_name) + '">' + safe_fail_name + '</a>'
                        ]),
                    });
                }
            });
        }
    },
});

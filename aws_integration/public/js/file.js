frappe.ui.form.on("File", {
    refresh: function (frm) {
        if (frm.doc.is_on_s3 && frm.doc.s3_key) {
            // Add S3 indicator
            let label = frm.doc.local_deleted
                ? __("Stored on S3 (local deleted)")
                : __("Stored on S3");
            frm.dashboard.set_headline(
                `<span class="indicator-pill green">${label}</span>`
            );
        } else if (!frm.doc.is_on_s3 && frm.doc.file_url && frm.doc.file_url.startsWith("/")) {
            frm.add_custom_button(__("Upload to S3"), function () {
                frappe.call({
                    method: "aws_integration.api.s3.upload_single_file_to_s3",
                    args: { file_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Queuing file for S3 upload..."),
                    callback: function (r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __("File queued for S3 upload. The form will refresh automatically when complete."),
                                indicator: "blue",
                            }, 7);
                        } else {
                            frappe.msgprint({
                                title: __("Error"),
                                indicator: "red",
                                message: r.message
                                    ? r.message.message
                                    : __("Failed to queue file for S3 upload."),
                            });
                        }
                    },
                    error: function () {
                        frappe.msgprint({
                            title: __("Error"),
                            indicator: "red",
                            message: __("Failed to queue file for S3 upload."),
                        });
                    },
                });
            });
        }

        // Refresh the form when this specific file finishes uploading to S3
        // in the background. Use .off() to prevent duplicate listeners on refresh.
        frappe.realtime.off("s3_upload_complete");
        frappe.realtime.on("s3_upload_complete", function (data) {
            if (data.file_name === frm.doc.name) {
                frm.reload_doc();
            }
        });
    },
});

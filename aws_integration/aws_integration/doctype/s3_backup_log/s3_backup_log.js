// Copyright (c) 2026, Hybrowlabs Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("S3 Backup Log", {
	refresh(frm) {
		const FILE_FIELDS = [
			"db_file_url",
			"site_config_url",
			"files_archive_url",
			"private_archive_url",
		];

		FILE_FIELDS.forEach((fieldname) => {
			appendDownloadIcon(frm, fieldname);
		});

		["db_size", "files_size", "total_size"].forEach((fieldname) => {
			formatSizeField(frm, fieldname);
		});

		// Show "Delete Local Files" button if backup is on S3 but local copies exist
		if (frm.doc.status === "Success" && frm.doc.s3_bucket && !frm.doc.local_cleaned && frm.doc.local_backup_paths) {
			frm.add_custom_button(__("Delete Local Files"), function () {
				frappe.confirm(
					__("This will permanently delete local backup files. Continue?"),
					function () {
						frappe.call({
							method: "aws_integration.s3.backup.cleanup_backup_local_files",
							args: { log_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Deleting local files..."),
							callback: function () {
								frm.reload_doc();
							},
						});
					}
				);
			});
		}
	},
});

function appendDownloadIcon(frm, fieldname) {
	const field = frm.fields_dict[fieldname];
	const $wrapper = field.$wrapper;

	$wrapper.find(".s3-download-icon").remove();

	if (!frm.doc[fieldname]) return;

	// Read-only fields show .control-value, editable fields show .control-input
	const $target = $wrapper.find(".control-value").is(":visible")
		? $wrapper.find(".control-value")
		: $wrapper.find(".control-input");

	$target.css({position: "relative"});

	const $icon = $(`
		<a class="s3-download-icon" title="${__("Download from S3")}" style="
			position: absolute;
			right: 8px;
			top: 50%;
			transform: translateY(-50%);
			cursor: pointer;
			z-index: 1;
			font-size: 14px;
			color: var(--text-muted);
		"><i class="fa fa-download"></i></a>
	`);

	$icon.on("mouseenter", function () {
		$(this).css("color", "var(--primary)");
	}).on("mouseleave", function () {
		$(this).css("color", "var(--text-muted)");
	});

	$icon.on("click", async (e) => {
		e.preventDefault();
		$icon.find("i").removeClass("fa-download").addClass("fa-spinner fa-spin");
		try {
			const res = await frappe.call({
				method: "aws_integration.s3.backup.get_backup_download_url",
				args: {
					log_name: frm.doc.name,
					file_field: fieldname,
				},
			});

			if (res.message && res.message.url) {
				window.open(res.message.url, "_blank");
			} else {
				frappe.msgprint(__("Could not retrieve download URL."));
			}
		} catch (error) {
			frappe.msgprint(__("Failed to get download URL."));
			console.error(error);
		} finally {
			$icon.find("i").removeClass("fa-spinner fa-spin").addClass("fa-download");
		}
	});

	$target.append($icon);
}

function fmtSize(bytes) {
	if (!bytes) return "0 B";
	const units = ["B", "KB", "MB", "GB", "TB"];
	const i = Math.floor(Math.log(bytes) / Math.log(1024));
	return (bytes / Math.pow(1024, i)).toFixed(1) + " " + units[i];
}

function formatSizeField(frm, fieldname) {
	const val = frm.doc[fieldname];
	if (!val) return;
	const $el = frm.fields_dict[fieldname].$wrapper
		.find(".like-disabled-input, .control-value");
	if ($el.length) {
		$el.first().text(fmtSize(val));
	}
}

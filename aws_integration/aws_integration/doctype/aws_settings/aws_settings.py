# Copyright (c) 2024, Hybrowlabs Technologies and contributors
# For license information, please see license.txt
import boto3
import frappe
from frappe import _
from botocore.exceptions import ClientError
from frappe.model.document import Document
from aws_integration.utils import validate_email


class AWSSettings(Document):

    def before_save(self):
        self.handle_email_flush()

    def get_ses_client(self):
        aws_secret_access_key = self.get_password("aws_secret_access_key")
        return boto3.client(
            "sesv2",
            region_name=self.region,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    def validate(self):
        if self.source_email and not validate_email(self.source_email):
            frappe.throw("Please enter valid email address")

    def send_email(
        self,
        destinations,
        subject,
        content=None,
        html=None,
        reply_tos=None,
    ):
        """
        Sends emails in batches with a rate limit of 25 per second.

        :param destinations: List of destinations (objects with `to_service_format` method).
        :param subject: Email subject.
        :param text: Plain text body (optional).
        :param html: HTML body (optional).
        :param reply_tos: List of reply-to addresses (optional).
        :param batch_size: Number of recipients per batch (default: 25).
        :return: List of message IDs or None for failed attempts.
        """
        self.source = f"{self.sender_name} <{self.source_email}>"
        self.ses_client = self.get_ses_client()
        send_args = {
            "FromEmailAddress": self.source,
            "Destination": destinations.to_service_format(),
            "Content": {
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {},
                }
            },
        }

        if content:
            send_args["Content"]["Simple"]["Body"]["Text"] = {
                "Data": content,
                "Charset": "UTF-8",
            }

        if html:
            send_args["Content"]["Simple"]["Body"]["Html"] = {
                "Data": html,
                "Charset": "UTF-8",
            }

        if reply_tos:
            send_args["ReplyToAddresses"] = reply_tos

        try:
            response = self.ses_client.send_email(**send_args)
            message_id = response.get("MessageId")
            if not message_id:
                frappe.throw(_("Failed to send email. Please try again."))
            self.add_ses_logs(subject, content or html, message_id, destinations)
            return response
        except ClientError as e:
            frappe.log_error(
                _("Failed to send email: {error}").format(error=str(e)),
                frappe.get_traceback(),
            )

    def add_ses_logs(self, subject, message, message_id, destinations):
        """Add SES logs after sending email."""
        ses_log = frappe.get_doc(
            {
                "doctype": "AWS SES Logs",
                "message_id": message_id,
                "subject": subject,
                "message": message,
                "status": "Sent",
                "from": self.source_email,
            }
        )
        recipients = (
            (destinations.tos or [])
            + (destinations.ccs or [])
            + (destinations.bccs or [])
        )
        ses_log.recepients = ", ".join(recipients)
        ses_log.insert()


    def handle_email_flush(self):
        methods = [
            ("frappe.email.queue.flush", not self.enable_aws),
            ("aws_integration.utils.email.flush_email_queue", self.enable_aws)
        ]
        
        for method, enable in methods:
            self.email_flush_handler(method, enable)
    
    def email_flush_handler(self, method_name, enable=True):
        """
        Enable or disable the email flush job.
        """
        try:
            job = frappe.get_doc("Scheduled Job Type", {"method": method_name})
            job.stopped = not enable
            job.save()
        except frappe.DoesNotExistError:
            frappe.log_error(
                f"Failed to disable {method_name} job. Please disable it manually.",
                frappe.get_traceback(),
            )
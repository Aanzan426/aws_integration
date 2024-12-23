import re
import time
import frappe
from frappe import _, cint
from itertools import islice


class SESDestination:
    """Contains data about an email destination."""

    def __init__(self, tos, ccs=None, bccs=None):
        self.tos = tos
        self.ccs = ccs
        self.bccs = bccs

    def to_service_format(self):
        svc_format = {"ToAddresses": self.tos}
        if self.ccs:
            svc_format["CcAddresses"] = self.ccs
        if self.bccs:
            svc_format["BccAddresses"] = self.bccs
        return svc_format


def validate_email(email):
    """Regular expression to validate email addresses."""
    email_pattern = re.compile(r"[^@]+@[^@]+\.[^@]+")
    return bool(email_pattern.match(email))


def is_html(text):
    """Regular expression to check for HTML tags"""
    html_pattern = re.compile(r"<([a-zA-Z]+)[^>]*>(.*?)</\1>|<([a-zA-Z]+)[^>]*>")
    return bool(html_pattern.search(text))


def chunk(iterable, size):
    """Yield successive chunks of a specified size from an iterable."""
    iterator = iter(iterable)
    for first in iterator:
        yield [first, *islice(iterator, size - 1)]


def sendmail(subject, message, recepient, cc_recepient, bcc_recepient, reply_tos=None):
    email_sender = frappe.get_single("AWS Settings")
    destinations = SESDestination(tos=recepient, ccs=cc_recepient, bccs=bcc_recepient)

    email_params = {
        "destinations": destinations,
        "subject": subject,
        "reply_tos": reply_tos,
    }

    if is_html(message):
        email_params["html"] = message
    else:
        email_params["content"] = message

    return email_sender.send_email(**email_params)


def send_email_in_batches(data):
    """
    Structure of data:
    {
        "key_name": {
            "subject": "Subject",
            "content": "Content",
            "recepients": [],
            "cc_recepients": [],
            "bcc_recepients": [],
            reply_tos: []
        }
    }
    """
    email_batch_size = frappe.get_value(
        "AWS Settings", "AWS Settings", "email_batch_size"
    )

    for student_data in chunk(data.keys(), cint(email_batch_size)):
        for key in student_data:
            student = data[key]
            sendmail(
                student.get("subject"),
                student.get("content"),
                student.get("recepients"),
                student.get("cc_recepients"),
                student.get("bcc_recepients"),
            )
        time.sleep(1)

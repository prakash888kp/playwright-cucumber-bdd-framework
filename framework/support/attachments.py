"""Scenario attachments (text/screenshots) collected for the HTML report.
tests/conftest.py owns the manifest lifecycle; steps call attach_text().
"""


def attach_text(context, name: str, text: str):
    context.attachments.append({"type": "text/plain", "name": name, "text": text})

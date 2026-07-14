"""Scenario attachments (text/screenshots) collected for the HTML report.
environment.py owns the manifest lifecycle; steps call attach_text().
"""


def attach_text(context, name: str, text: str):
    context.attachments[context.scenario_key].append(
        {"type": "text/plain", "name": name, "text": text}
    )

"""Minimales Logging auf stderr – stdout gehört der eigentlichen Antwort."""

import sys


def warn(message):
    print(f"reveries: {message}", file=sys.stderr)

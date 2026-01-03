"""Django management command for primitivesctl."""

import sys

from django.core.management.base import BaseCommand

from primitives_testbed.terminal_ui.cli import cli


class Command(BaseCommand):
    help = "Terminal UI for browsing and managing django-primitives data"

    def add_arguments(self, parser):
        parser.add_argument("cli_args", nargs="*", metavar="args")

    def handle(self, *args, **options):
        cli_args = list(options.get("cli_args", []))
        if not cli_args:
            cli_args = ["--help"]
        try:
            cli(args=cli_args, standalone_mode=True)
        except SystemExit as e:
            if e.code != 0:
                sys.exit(e.code)

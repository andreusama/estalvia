"""`runserver` que solo escucha en 127.0.0.1: la web local no se expone a la red (spec #18)."""
import re

from django.core.management.base import CommandError
from django.core.management.commands.runserver import Command as RunserverCommand

LOCAL = re.compile(r"^(?:(?:127\.0\.0\.1|localhost):)?\d+$")


class Command(RunserverCommand):
    default_addr = "127.0.0.1"

    def handle(self, *args, **options):
        direccion = options.get("addrport") or ""
        if options.get("use_ipv6") or (direccion and not LOCAL.match(direccion)):
            raise CommandError("esta web solo escucha en 127.0.0.1 (ejemplo: runserver 8000)")
        return super().handle(*args, **options)

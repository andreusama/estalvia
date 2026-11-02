#!/usr/bin/env python
"""Arranque de la web local del copiloto energético: `python manage_energia.py runserver` (solo 127.0.0.1; ver .env.example). NO es la plataforma desplegada: ver `manage.py` y docs/adr/0001."""
import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "estalvia.web.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

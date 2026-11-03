#!/usr/bin/env python
"""Plataforma Estalvia (la que se despliega en Vercel): `python manage.py runserver`."""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plataforma.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

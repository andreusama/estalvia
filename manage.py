#!/usr/bin/env python
"""Plataforma Estalvia (la que se despliega en Vercel): `python manage.py runserver`.

El copiloto energético, que solo corre en local, se arranca con `python manage_energia.py` (docs/adr/0001).
"""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plataforma.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

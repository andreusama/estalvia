"""Paso de construcción en Vercel: aplica las migraciones si hay base de datos configurada (DATABASE_URL)."""

import os
import subprocess
import sys

if os.environ.get("DATABASE_URL"):
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], check=True)
else:
    print("build.py: sin DATABASE_URL, no se migra (el Bar avisará de que falta la base de datos).")

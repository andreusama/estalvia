"""Crea una cuenta (o cambia su contraseña) y, si se pide, le da los datos que existían antes de las cuentas.

python manage.py crear_usuario nombre [--adoptar]

La contraseña se pide por teclado (no queda en el historial del terminal). `--adoptar` asigna a esa cuenta los
documentos, proveedores y perfiles del banco que no eran de nadie: es la forma de recuperar lo subido antes.
"""

from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from prototipos.bar.models import Documento, PerfilImportacion, Proveedor


class Command(BaseCommand):
    help = "Crea un usuario (o cambia su contraseña); con --adoptar recibe los datos anteriores a las cuentas."

    def add_arguments(self, parser):
        parser.add_argument("nombre")
        parser.add_argument("--adoptar", action="store_true", help="Quedarse con los datos que no son de nadie")

    def handle(self, *args, nombre, adoptar, **opts):
        Usuario = get_user_model()
        usuario = Usuario.objects.filter(username=nombre).first()
        if usuario is None or not adoptar:
            clave = getpass("Contraseña: ")
            if clave != getpass("Repite la contraseña: "):
                raise CommandError("Las contraseñas no coinciden.")
            try:
                validate_password(clave, usuario or Usuario(username=nombre))
            except ValidationError as e:
                raise CommandError(" ".join(e.messages)) from None
            if usuario is None:
                usuario = Usuario.objects.create_user(username=nombre, password=clave)
                self.stdout.write(self.style.SUCCESS(f"Usuario «{nombre}» creado."))
            else:
                usuario.set_password(clave)
                usuario.save()
                self.stdout.write(self.style.SUCCESS(f"Contraseña de «{nombre}» cambiada."))
        if adoptar:
            for modelo in (Documento, Proveedor, PerfilImportacion):
                n = modelo.objects.filter(propietario__isnull=True).update(propietario=usuario)
                self.stdout.write(f"{modelo._meta.verbose_name_plural}: {n} asignados a «{nombre}».")

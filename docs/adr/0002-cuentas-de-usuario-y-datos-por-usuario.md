# Cuentas de usuario, registro por invitación y datos separados por usuario

Sustituye la contraseña única de la plataforma por cuentas (`django.contrib.auth`, nombre de usuario y contraseña de 10+ caracteres). Cada documento, proveedor y perfil del banco guarda su `propietario`; los movimientos y los pagos cuelgan de ellos. Toda consulta del Bar se filtra por el usuario que ha entrado, y un objeto de otra persona responde 404 (no «prohibido»), para no confirmar que existe.

Las cuentas se crean de dos maneras: `manage.py crear_usuario nombre` (pide la contraseña por teclado) o `/registro/` con el código de invitación de la variable `ESTALVIA_CODIGO_INVITACION`. Sin esa variable el registro está cerrado. Quien comparte el enlace comparte también el código.

Lo anterior a las cuentas (propietario nulo) no lo ve nadie hasta que `crear_usuario nombre --adoptar` se lo asigna a una cuenta.

## Consecuencias

- Una sola base de datos compartida, con separación **por código**, no por esquema ni por base: un olvido de `propietario=` en una consulta nueva filtraría datos. Los tests de `test_usuarios.py` cubren cada pantalla y acción; una vista nueva debe entrar ahí.
- La clave de Anthropic sigue siendo una sola: las lecturas de todos las paga quien despliega.
- Sin límite de intentos de entrada (las funciones de Vercel no comparten memoria). Aceptable con pocas cuentas y contraseñas largas; hay que añadirlo antes de abrirlo al público.
- Sin recuperación de contraseña por correo: la cambia quien administra con `crear_usuario nombre`.
- Los datos de cada persona pueden verse en la base de datos por quien la administra. El consentimiento sobre fotos y extractos reales sigue la ADR 0001 del Bar.

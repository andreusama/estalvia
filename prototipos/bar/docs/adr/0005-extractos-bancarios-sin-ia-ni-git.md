# Los extractos bancarios los lee el código, no la IA, y no entran en git

El extracto (CSV) se interpreta con reglas escritas en código y un perfil configurable por banco (separador, formato de fecha y de números, nombres de columna); no se envía a la API de Anthropic ni a ningún tercero. Los importes se leen como decimales exactos y una cifra que no encaja con el formato elegido se rechaza con su número de línea en vez de adivinarse. Reimportar un fichero no duplica movimientos (huella por perfil, fecha, concepto, importe, saldo y orden de aparición ese día, para no perder un cobro doble real).

Solo un importe idéntico, sin tolerancia, se propone como pago; lo parecido se enseña como pista con su explicación y nunca se da por pagado. Confirmar siempre lo hace una persona, y el servidor vuelve a comprobar la propuesta al confirmar.

No se guardan credenciales del banco ni el número de cuenta completo (solo las 4 últimas cifras). Los extractos reales nunca van a git (`.gitignore`) y los tests usan extractos inventados.

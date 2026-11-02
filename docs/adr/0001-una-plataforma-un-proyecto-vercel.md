# Una plataforma, un proyecto de Vercel, una app Django por prototipo

Estalvia se despliega como un único proyecto de Vercel sobre este repo (Root Directory `.`), no uno por prototipo. Un proyecto Django en la raíz (`plataforma/`: ajustes, `urls.py`, `wsgi.py`) monta cada prototipo como una app autocontenida bajo su prefijo de URL (`/bar/`, y `/energia/` más adelante); en `/` hay una página con la lista de apps. Cada prototipo vive como paquete en `prototipos/<nombre>/` (modelos, vistas, plantillas, estáticos, `urls`) para poder separarlo cuando funcione. El `manage.py` de la raíz apunta a la plataforma (Vercel lo busca ahí) y el del copiloto energético pasa a `manage_energia.py`.

El copiloto energético **no se monta** en la plataforma todavía: sin base de datos, solo local y bajo la regla de datos sintéticos, publicarlo expondría facturas de luz.

## Consecuencias

- Las apps comparten una PostgreSQL (tablas separadas por app), un almacén Blob (rutas con prefijo por app), una clave de Anthropic y una contraseña única de plataforma. Es válido mientras haya un solo cliente real; con datos de empresas distintas hay que revisar usuarios y separación de datos.
- Un fallo de una app puede tumbar el despliegue de todas.

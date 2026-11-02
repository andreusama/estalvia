---
status: partly superseded by docs/adr/0001-una-plataforma-un-proyecto-vercel.md (el proyecto de Vercel es el de la plataforma, no uno propio del bar)
---

# Despliegue en Vercel con PostgreSQL y almacenamiento de objetos

Las funciones de Vercel no tienen disco persistente, así que SQLite y las fotos en carpeta solo valen en local. En producción se usa PostgreSQL gestionado y almacenamiento de objetos privado para los originales; en local, SQLite y una carpeta ignorada por git, elegidos por variable de entorno. La extracción se lanza un documento por petición, con estado visible, para no depender de límites de tiempo largos; el comando de gestión procesa carpetas enteras en local. El acceso es una única contraseña compartida sobre HTTPS, con protección de despliegues activada; usuarios reales vendrán después. Esto sustituye el «SQLite y más adelante PostgreSQL» y el «sin despliegue» del encargo inicial.

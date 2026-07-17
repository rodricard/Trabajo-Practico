# ListMeApp

Tablero de tareas estilo Trello hecho con Django: tableros, listas y tarjetas organizadas por drag & drop, grupos de trabajo, chat por tablero y notificaciones en tiempo real vía WebSockets (Django Channels).

## Funcionalidades

- **Tableros, listas y tarjetas** con permisos por usuario (cada uno ve solo los tableros de los que es miembro) y roles por tablero (propietario / admin / miembro).
- **Drag & drop** de tarjetas y listas, con posiciones ordenadas y actualización en vivo para todos los que estén mirando el tablero.
- **Asignación de tarjetas**, estados (pendiente / en proceso / completado), fecha límite y descripción.
- **Checklists** (subtareas) dentro de cada tarjeta, con barra de progreso.
- **Comentarios** en tarjetas, con edición, borrado y **menciones `@usuario`** que generan notificación al mencionado.
- **Etiquetas** por tablero (crear, asignar/quitar de tarjetas, eliminar).
- **Archivar en vez de eliminar**: listas y tarjetas se archivan primero y se pueden restaurar o borrar definitivamente después.
- **Historial de actividad** por tablero (quién hizo qué y cuándo).
- **Indicador de presencia en vivo**: muestra quién está viendo el tablero en ese momento.
- **Buscador global** de tarjetas por título, descripción, lista o tablero.
- **Chat por tablero**, con bloqueo del chat por parte de los administradores.
- **Grupos de trabajo**, con solicitudes de ingreso, aprobación/rechazo y roles.
- **Notificaciones en tiempo real** (campanita con dropdown, agrupado de ráfagas, toasts) vía WebSockets.
- **Perfil de usuario** editable (foto, nombre de usuario, correo, contraseña) y modo oscuro.
- **Panel de superadministración**, con estadísticas y gestión de usuarios.
- **API REST** (Django REST Framework) para tableros, tarjetas, grupos y notificaciones, con autenticación por token.

## Stack técnico

- Django 6 + Django Channels (WebSockets sobre ASGI, vía `daphne`)
- Django REST Framework (API + autenticación por token)
- SQLite (desarrollo)
- HTML/CSS/JS plano en el frontend (sin framework de JS), con [SortableJS](https://github.com/SortableJS/Sortable) para el drag & drop

## Requisitos

- Python 3.12+
- Un entorno virtual (`venv`)

## Instalación

```bash
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux / macOS

pip install -r requirements.txt
```

Copiá `.env.example` a `.env` y completá los valores (como mínimo `SECRET_KEY`):

```bash
cp .env.example .env
```

Aplicá las migraciones:

```bash
python manage.py migrate
```

Creá un usuario para probar la app:

```bash
python manage.py createsuperuser
```

Para acceder al panel de superadministración de la app (`/accounts/superadmin/`), ese usuario además necesita el flag `is_superadmin` marcado en su perfil — se activa desde `/admin/` (Django admin) en el modelo `UserProfile`, o llamando a la vista de superadmin con otro usuario que ya lo tenga.

## Levantar el servidor

El proyecto usa [Django Channels](https://channels.readthedocs.io/) para servir WebSockets (drag & drop en vivo, notificaciones en vivo) además del HTTP normal. Para desarrollo, alcanza con el comando de siempre de Django — Channels se integra automáticamente:

```bash
python manage.py runserver
```

No uses `daphne` directamente en desarrollo: no sirve los archivos estáticos por sí solo. `manage.py runserver` ya sabe manejar HTTP, estáticos y WebSockets juntos.

## Tests

```bash
python manage.py test accounts boards groups
```

## WebSockets

- `ws/boards/<board_id>/` — cambios en vivo del tablero (tarjetas y listas creadas, movidas, editadas, eliminadas, y presencia de quién lo está viendo).
- `ws/notifications/` — notificaciones en vivo del usuario autenticado (badge de la campanita, asignaciones, invitaciones a tableros/grupos, menciones).

En producción, `CHANNEL_LAYERS` debería apuntar a un backend real (por ejemplo Redis vía `channels_redis`) en lugar del `InMemoryChannelLayer` usado en desarrollo, para que los mensajes se propaguen entre múltiples procesos/workers.

## API REST

Base: `/api/`. Requiere autenticación por token (`POST /api/token/` con usuario y contraseña para obtenerlo, luego mandarlo como header `Authorization: Token <token>`).

- `GET/POST /api/boards/` — listar/crear tableros propios.
- `GET /api/boards/<id>/` — detalle de un tablero.
- `GET/PATCH /api/cards/<id>/` — detalle y edición parcial de una tarjeta.
- `GET /api/cards/` — tarjetas asignadas al usuario autenticado.
- `GET /api/stats/` — estadísticas generales (solo superadmins).
- `GET /api/groups/`, `GET /api/notifications/` — grupos y notificaciones del usuario.

# Tableo

Tablero de tareas estilo Trello hecho con Django, con tableros, listas y tarjetas organizadas por drag & drop, grupos de trabajo y notificaciones en tiempo real vía WebSockets (Django Channels).

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

## Levantar el servidor

El proyecto usa [Django Channels](https://channels.readthedocs.io/) para servir WebSockets (drag & drop en vivo, notificaciones en vivo) además del HTTP normal. Para desarrollo, alcanza con el comando de siempre de Django — Channels se integra automáticamente:

```bash
python manage.py runserver
```

No uses `daphne` directamente en desarrollo: no sirve los archivos estáticos por sí solo. `manage.py runserver` ya sabe manejar HTTP, estáticos y WebSockets juntos.

## WebSockets

- `ws/boards/<board_id>/` — cambios en vivo del tablero (tarjetas y listas creadas, movidas, editadas o eliminadas).
- `ws/notifications/` — notificaciones en vivo del usuario autenticado (badge de la campanita, asignaciones, invitaciones a tableros/grupos).

En producción, `CHANNEL_LAYERS` debería apuntar a un backend real (por ejemplo Redis vía `channels_redis`) en lugar del `InMemoryChannelLayer` usado en desarrollo, para que los mensajes se propaguen entre múltiples procesos/workers.

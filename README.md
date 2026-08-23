# TODOlist

Aplicación web de gestión de tareas, proyectos y productividad personal.
MVP orientado a crecer hacia un **LifeOS** (tareas + proyectos + Kanban +
calendario + hábitos + objetivos + IA).

> Repositorio: https://github.com/ToDoSolutions/TODOlist.git

## Stack

| Capa        | Tecnología                                              |
|-------------|---------------------------------------------------------|
| Frontend    | React + TypeScript + Vite + MUI + TanStack Query + Zod  |
| Backend     | Django + Django REST Framework + SimpleJWT              |
| Base datos  | PostgreSQL                                              |
| Caché/Cola  | Redis                                                   |
| Contenedores| Docker + Docker Compose                                 |

## Alcance MVP

- **Autenticación**: registro, login, JWT (access + refresh).
- **Proyectos**: crear, listar, archivar.
- **Tareas**: CRUD completo, título, descripción, estado, prioridad, fecha límite.
- **Subtareas**: checklist dentro de una tarea.
- **Estados**: backlog, pendiente, en progreso, bloqueada, en revisión,
  completada, cancelada, archivada.
- **Prioridades**: P0 Crítica → P5 Algún día.
- **Etiquetas**: personalizadas y coloreadas.
- **Filtros**: por estado, prioridad, etiqueta y fecha.
- **Vistas**: Lista y Kanban.

## Estructura

```
TODOlist/
├── backend/      # Django + DRF
├── frontend/     # React + Vite
├── docker-compose.yml
└── README.md
```

## Puesta en marcha (desarrollo)

Requisitos: Docker y Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/api/
- Admin Django: http://localhost:8000/admin/

## Variables de entorno

Ver [`.env.example`](./.env.example).

## Licencia

MIT — ver [LICENSE](./LICENSE).

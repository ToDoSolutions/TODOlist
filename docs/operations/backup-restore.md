# Backup y restauración

Datos con estado real: **PostgreSQL** (todo lo transaccional) y
**`backend/media/`** (attachments, avatares). Redis es reconstruible
(cache, colas Celery, estados OAuth efímeros).

## Backup

```bash
# Postgres (diario cubre el RPO de 24 h de slo.md)
docker compose exec db pg_dump -U todolist todolist \
  | gzip > backup-$(date +%F).sql.gz

# Media
tar -czf media-$(date +%F).tar.gz backend/media/
```

Para RPO más fino: WAL archiving (PITR) en vez de dumps.

## Restauración — probada, no solo creada

Un backup no probado no es un backup. Verificar al menos trimestralmente:

```bash
# 1. Restaurar en una instancia limpia (NO sobre producción)
docker compose up -d db
cat backup-YYYY-MM-DD.sql.gz | gunzip | \
  docker compose exec -T db psql -U todolist todolist

# 2. Levantar el resto y verificar
docker compose up -d
curl -fsS http://localhost:8000/api/health/ready/

# 3. Comprobar integridad funcional
#    - login de un usuario conocido
#    - GET /api/tasks/ devuelve datos
#    - attachments en media/ se descargan (URL autorizada)
# 4. Medir el tiempo total → alimenta el RTO declarado en slo.md
```

## Corrupción de datos

- Sync offline usa `version` por tarea — un restore atrasado puede
  generar conflictos legítimos; el merge por campo los resuelve sin
  pérdida silenciosa.
- E2EE: el servidor solo guarda ciphertext — perder la clave privada del
  dispositivo es pérdida de datos irrecuperable **por diseño** (ver
  `docs/security/e2ee-threat-model.md`); la rotación conserva la clave
  pública anterior para que shares antiguos sigan descifrables.

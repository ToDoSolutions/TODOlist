# Cómo contribuir

Gracias por tu interés. Este documento cubre el flujo de desarrollo;
la arquitectura y decisiones de diseño viven en `AGENTS.md` y `docs/`.

## Setup local

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver                      # :8000

# Frontend (otra terminal)
cd frontend && npm install && npm run dev       # :5173
```

Con Docker: `docker compose up` (ver README). Datos demo: `SEED_DEV=1`.

## Antes de abrir un PR

```bash
# Backend
cd backend
ruff check apps config --select E9,F,SIM,I001 --exclude "*/migrations/*"
bandit -r apps config -x "*/migrations/*,tests" -lll
python -m pytest tests/ -n 8 -q     # ~10 min; en serie ~30 min

# Frontend
cd frontend
npx tsc -b --noEmit
npx eslint .
npx vitest run
npm run build
```

Toda la lógica compartida va por la capa de servicio
(`apps/tasks/services.py`, `apps/projects/models.accessible_projects`);
los permisos de escritura se validan server-side con `write=True` en
**todos** los canales (REST, GraphQL, CalDAV, MCP, offline sync).

## Convenciones

- Código y comentarios en español o inglés consistente con el archivo.
- Commits pequeños con mensaje que explique el *porqué*.
- Tests obligatorios para fixes de permisos/autorización (casos + y −).
- Migraciones reversibles; nunca editar una migración ya mergeada.
- Nada de secretos en el repo — `.env` está en `.gitignore`; usa
  `.env.example` para documentar variables nuevas.

## Issues

- Bugs: pasos para reproducir, comportamiento actual vs esperado, entorno.
- Features: qué problema resuelve y criterios de aceptación.
- Seguridad: **no** abras issue público — ver `SECURITY.md`.

## Definition of Done

Un cambio está terminado cuando:

- [ ] El requisito/criterio de aceptación está cumplido y verificable
- [ ] Código revisado (PR) — diseño, complejidad, errores, concurrencia
- [ ] Tests cubren el comportamiento y los casos de error; los de
      autorización verifican + y −
- [ ] Lint + typecheck + tests pasan en CI
- [ ] Sin secretos ni datos sensibles en logs
- [ ] Migraciones reversibles si aplica
- [ ] `CHANGELOG.md` actualizado si el cambio es visible
- [ ] Docs relevantes actualizadas (README, AGENTS.md, ADR si es
      una decisión nueva)
- [ ] Reversible: rollback o roll-forward posible

## Definition of Ready

Antes de desarrollar una funcionalidad:

- [ ] Problema y usuario identificados, alcance delimitado
- [ ] Criterios de aceptación escritos
- [ ] Riesgos y dependencias conocidos
- [ ] Requisitos de seguridad/accesibilidad identificados
- [ ] Métrica de éxito definida si es user-facing

## Revisión de código

El revisor comprueba (orden de importancia):

1. ¿Resuelve el requisito declarado?
2. ¿El diseño es el más sencillo que funciona? ¿Duplica algo?
3. ¿Respeta la frontera de autorización (ADR-001: `write=True` en
   mutaciones) y la capa de servicio (ADR-004)?
4. ¿Los errores se manejan? ¿Hay problemas de concurrencia?
5. ¿Las entradas se validan? ¿Se exponen datos sensibles en logs/respuestas?
6. ¿Los tests cubren el comportamiento y los errores?
7. ¿Puede revertirse? ¿Introduce incompatibilidades o coste operativo nuevo?

Clasificación de comentarios: **bloqueante** (bug, seguridad, pérdida de
datos, diseño insostenible) · **importante** (debería corregirse) ·
**sugerencia** · **pregunta** · **nit**.

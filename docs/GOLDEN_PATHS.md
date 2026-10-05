# Golden paths — cómo se hace una tarea común aquí

La forma recomendada de implementar operaciones frecuentes. Seguirla
evita drift entre canales y hace que los reviewers puedan verificar el
cambio rápido.

## Añadir un campo a una tarea

1. Modelo + migración (`makemigrations`) — migración reversible.
2. `apps/tasks/services.py`: si es editable, el campo entra en
   `update_task` (canal único — paridad automática en REST/GraphQL/
   CalDAV/MCP/offline sync/automatizaciones).
3. Serializer REST + `TaskType` GraphQL (campo explícito si el modelo
   lo exige).
4. Frontend: `types.ts` + formulario en `TaskDialog` + API helper.
5. Tests: `test_services.py` o el fichero del canal afectado.

## Añadir un endpoint REST

1. ViewSet en `apps/<app>/views.py` — `permission_classes` explícito.
2. Queryset con `for_user(...)` / `accessible_projects(...)` —
   `write=True` si muta. Nunca `objects.all()` sin scoping.
3. Serializer en `serializers.py`.
4. Registrar en `urls.py`.
5. Tests: autorización +/− (`test_users_security_extended.py` o fichero
   del módulo) + caso feliz.

## Crear una migración de datos no trivial

1. Añadir estructura nueva compatible (migración schema).
2. Código que lee/escribe ambas (feature flag si es arriesgado).
3. `RunPython` con lotes si el volumen puede ser grande.
4. Verificación post-migración (check o test).
5. Roll-forward plan — rollback de datos no existe.

## Añadir una automatización trigger/acción

1. Trigger en `apps/automations/` + señal o beat que lo dispara.
2. Acción en `engine.py` — fallo = `{"error": ...}` → FAILED, nunca SUCCESS.
3. Valida en serializer (`action`/`trigger` válidos).
4. Scope: regla evaluada solo contra `task.owner` — nunca el actor.
5. Test: trigger dispara + acción efecto observable.

## Emitir un evento de dominio

1. `OutboxEvent` se crea dentro de la transacción del cambio (no después).
2. Handler registrado en `apps/events/handlers.py` — efectos externos
   (WS push, webhook, chat) van ahí, nunca en el request.
3. Internos baratos (AuditLog, Notification) pueden quedar síncronos.

## Añadir una feature flag

1. `FEATURE_FLAGS` en settings con default `True`.
2. `FeatureFlagMiddleware` gatea por prefijo de URL.
3. Registra propósito + fecha prevista de retirada en TECH_DEBT si
   es temporal — un flag sin caducidad es deuda.

## Escribir un test nuevo

- Backend: `backend/tests/test_<area>.py`, `pytest.mark.django_db`;
  tests de permisos verifican + y −.
- Frontend: `src/**/__tests__/*.test.tsx`, vitest + i18n setup.
- Contrato: schemathesis cubre el OpenAPI — añade el endpoint al
  schema y ya está cubierto.

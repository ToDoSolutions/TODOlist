# Registro de riesgos

| ID | Riesgo | Categoría | Prob. | Impacto | Mitigación | Revisión |
|---|---|---|---|---|---|---|
| R-01 | Bypass de autorización en canal no-REST | seguridad | media | alto | `for_user(write=True)` única frontera + tests +/− por canal (ADR-001) | continua |
| R-02 | E2EE: pérdida de privada = datos irrecuperables | datos | media | alto | Backup cifrado con passphrase; rotación conserva clave anterior; documentado al usuario | por release |
| R-03 | Webhook entrante con firma válida de repo ajeno | seguridad | baja | alto | Scoping por installation+repo del payload + dedup por delivery id | continua |
| R-04 | OAuth account takeover por email no verificado | seguridad | baja | alto | `/user/emails` verificados; alias `@github.local` si no | continua |
| R-05 | xdist Windows worker crashes ocultan fallos reales | operación | media | medio | `--max-worker-restart`; run serial de confirmación antes de release | mensual |
| R-06 | Dependencias de test con vulns conocidas (pytest, starlette, setuptools) | dependencias | baja | bajo | `pip-audit` en CI; no afectan runtime; revisar al actualizar schemathesis | por release |
| R-07 | Backups sin restaurar nunca → RTO ficticio | recuperación | media | alto | `backup-restore.md` exige restauración probada en instancia limpia trimestral | trimestral |
| R-08 | Bus factor 1 — repo mantenido por una persona | equipo | alta | medio | AGENTS.md + ADRs + CONTRIBUTING.md documentan decisiones y setup | trimestral |
| R-09 | Rate limiting permite brute force en intake/forms públicos | seguridad | baja | medio | Throttles por scope dedicados (registro, reset, intake, account) | continua |
| R-10 | E2EE false confidence: usuarios creen que el servidor ve contenido cifrado | privacidad | baja | medio | Threat model público (`docs/security/e2ee-threat-model.md`) dice qué protege y qué no | continua |

Regla: un riesgo `alto` impacto sin mitigación documentada bloquea el
release. Las excepciones se registran aquí con fecha de revisión.

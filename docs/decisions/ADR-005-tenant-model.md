# ADR-005: Organización → Proyecto → Tarea con roles propagados

## Contexto

Se necesitaba colaboración multi-equipo sin que cada proyecto sea una
isla de permisos (y con SSO/SAML por dominio a nivel organización).

## Decisión

`Organization` + `OrganizationMembership` (owner/admin/member/guest) como
tenant raíz opcional; `Project.organization` opcional. owner/admin de
org → escritura en todos los proyectos; member → lectura; guest → sin
acceso implícito. Propagado a `accessible_projects` y `for_user` —
misma frontera que ADR-001.

## Consecuencias

+ Jerarquía clara sin duplicar reglas por nivel.
+ SSO (`sso_domain`/`sso_required`) se exige a nivel org.
+ La org es opcional: usuarios individuales no pagan el coste
  conceptual (proyectos sin org funcionan igual).

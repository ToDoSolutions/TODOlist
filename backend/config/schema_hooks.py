"""Postprocessing hooks para drf-spectacular.

La API exige autenticación globalmente (IsAuthenticated), por lo que
cualquier endpoint protegido puede responder 401/403. El schema generado
no los incluía por defecto — este hook los añade a toda operación que
declare security, para que el contrato publicado sea completo.
"""

_ERROR_SCHEMA = {
    "type": "object",
    "properties": {"detail": {"type": "string"}},
    "required": ["detail"],
}


def _error_response(description):
    return {
        "description": description,
        "content": {"application/json": {"schema": _ERROR_SCHEMA}},
    }


# Los errores de validación de DRF usan {"campo": ["error"]} o
# {"detail": "..."} / {"non_field_errors": [...]} según el serializer —
# schema permisivo para no romper el contrato con falsos positivos.
def _validation_response(description):
    return {
        "description": description,
        "content": {"application/json": {"schema": {"type": "object"}}},
    }


def add_auth_responses(result, generator, request, public):
    """Añade 401/403 a las operaciones con seguridad y 404 a las que
    tienen path params (cualquier id puede no existir)."""
    for path, path_item in result.get("paths", {}).items():
        has_id_param = "{" in path
        for operation in path_item.values():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            responses = operation.setdefault("responses", {})
            # 401 aplica a TODO endpoint: credenciales inválidas en login,
            # token ausente/expirado en endpoints protegidos
            responses.setdefault("401", _error_response("No autenticado"))
            # Cualquier endpoint con body puede devolver 400 de validación
            # (p.ej. JWT refresh con payload inválido devuelve 400, no 401)
            if operation.get("requestBody"):
                responses.setdefault("400", _validation_response("Petición inválida"))
            if operation.get("security"):
                responses.setdefault("403", _error_response("Permiso denegado"))
            if has_id_param:
                responses.setdefault("404", _error_response("No encontrado"))
            # Cualquier endpoint puede ser throttled (rate limiting global)
            responses.setdefault("429", _error_response("Demasiadas peticiones"))
    return result

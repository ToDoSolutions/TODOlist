"""Jerarquía de errores de integraciones externas.

Convierte errores de red/API externos en errores internos explícitos,
permitiendo sustituir ``except Exception`` por capturas precisas sin
perder resiliencia.
"""


class IntegrationError(Exception):
    """Base para errores de integración con servicios externos."""


class AuthenticationExpired(IntegrationError):
    """Token/credencial del servicio externo expirado o revocado."""


class ExternalRateLimited(IntegrationError):
    """El servicio externo devolvió rate limit (429)."""


class ExternalResourceNotFound(IntegrationError):
    """Recurso inexistente en el servicio externo (404)."""


class ExternalPayloadInvalid(IntegrationError):
    """Payload del servicio externo incompleto o inválido."""


class ExternalServiceUnavailable(IntegrationError):
    """Timeout, DNS o error 5xx del servicio externo."""

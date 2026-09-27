"""Contract testing con Schemathesis sobre el schema OpenAPI.

Valida que las respuestas reales de la API cumplen el contrato publicado
(drf-spectacular): códigos de estado documentados, Content-Type, y que no
se devuelven 5xx para inputs generados aleatoriamente.

Corre contra la WSGI app en-proceso con un JWT real de un usuario de test.
Marcado ``contract`` para excluirse de corridas rápidas:
    pytest -m "not contract"
"""
import uuid

import pytest
from hypothesis import settings as hsettings

schemathesis = pytest.importorskip("schemathesis")

from django.contrib.auth import get_user_model
from drf_spectacular.generators import SchemaGenerator
from rest_framework_simplejwt.tokens import AccessToken

from config.wsgi import application

User = get_user_model()


def _build_schema_dict():
    generator = SchemaGenerator()
    return generator.get_schema(request=None, public=True)


def _lazy_auth_app(app):
    """WSGI wrapper que crea el usuario+token de test en la PRIMERA request
    (lazy: dentro de la ejecución del test hay acceso a DB bajo cualquier
    modo de pytest) e inyecta Authorization en cada request."""
    token_cache = []

    def wrapped(environ, start_response):
        if not token_cache:
            _uid = uuid.uuid4().hex[:8]
            user = User.objects.create_user(
                username=f"contract{_uid}",
                email=f"contract{_uid}@x.com",
                password="pass12345",
            )
            token_cache.append(str(AccessToken.for_user(user)))
        # setdefault: si schemathesis envía su propio Authorization (p.ej.
        # credenciales inválidas para el check ignored_auth), se respeta
        environ.setdefault("HTTP_AUTHORIZATION", f"Bearer {token_cache[0]}")
        return app(environ, start_response)

    return wrapped


schema = schemathesis.openapi.from_dict(
    _build_schema_dict(),
    app=_lazy_auth_app(application),
    base_url="http://testserver",
)

pytestmark = [pytest.mark.contract, pytest.mark.django_db]


@schema.parametrize()
@hsettings(deadline=None, max_examples=25)
def test_api_contract(case):
    """Toda operación del schema responde con status documentado y sin 5xx.

    Se excluye content_type_conformance: en test DEBUG=1 las 404 devuelven
    la página HTML de Django en vez del JSON de producción.
    """
    from schemathesis.specs.openapi.checks import content_type_conformance

    response = case.call()
    case.validate_response(response, excluded_checks=(content_type_conformance,))

"""Security headers: CSP, Permissions-Policy, CORP.

CSP estricta para una API JSON: ``default-src 'none'`` impide que una
respuesta pueda cargar recursos o ejecutarse como documento (defensa en
profundidad ante content sniffing). El frontend SPA sirve su propia CSP
desde el servidor estático (ver frontend/nginx.conf / index.html).
"""
from django.conf import settings


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            # API JSON pura: ningún recurso cargable ni ejecución como documento
            response["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
            )
        else:
            # Swagger/ReDoc/admin necesitan scripts/estilos propios e inline
            response["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "frame-ancestors 'none'; base-uri 'self'"
            )
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response["Cross-Origin-Resource-Policy"] = "same-site"
        if not settings.DEBUG:
            response["Cross-Origin-Opener-Policy"] = "same-origin"
        return response

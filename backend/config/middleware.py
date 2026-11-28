"""Middleware de identidad de cliente tras proxy inverso.

El backend solo es alcanzable vía nginx (publicado en 127.0.0.1:8001)
— el edge fija ``X-Forwarded-For: $remote_addr`` (IP real del cliente,
sin chain falsificable). Sin este middleware ``request.META
["REMOTE_ADDR"]`` sería la IP del proxy para TODAS las peticiones y
los ``AnonRateThrottle`` de DRF (login/register/password_reset/
intake/share) colapsarían a un único bucket global: un atacante
agota el cupo de todos y nadie puede autenticarse.

OJO: si el puerto se publica algún día, este middleware permite
falsear XFF — mantener el bind a loopback o revisar antes.
"""


class ClientIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            request.META["REMOTE_ADDR"] = xff.split(",")[0].strip()
        return self.get_response(request)

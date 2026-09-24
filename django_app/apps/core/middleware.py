class PermissionsPolicyMiddleware:
    """Django não tem uma setting nativa pra Permissions-Policy (ao contrário
    de HSTS/X-Frame-Options/Referrer-Policy, que já mapeiam direto pra
    settings.py) — porte do header manual que existia no main.py do FastAPI."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

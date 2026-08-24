"""Cliente de la API de GitHub usando GitHub App authentication.
Genera JWT, obtiene installation tokens y hace llamadas a la API REST/GraphQL.
"""
import time
import jwt
import requests
from django.conf import settings


class GitHubAppClient:
    """Cliente para autenticación como GitHub App (JWT + installation token)."""

    BASE_URL = "https://api.github.com"
    GRAPHQL_URL = "https://api.github.com/graphql"

    def __init__(self, installation_id=None):
        self.app_id = settings.GITHUB_APP_ID
        self.private_key = settings.GITHUB_APP_PRIVATE_KEY
        self.installation_id = installation_id
        self._installation_token = None

    def _generate_jwt(self):
        """Genera el JWT para autenticarse como GitHub App."""
        if not self.private_key:
            raise ValueError("GITHUB_APP_PRIVATE_KEY no configurado")
        payload = {
            "iat": int(time.time()) - 60,
            "exp": int(time.time()) + (10 * 60),
            "iss": self.app_id,
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    def _get_installation_token(self):
        """Obtiene un installation access token usando el JWT."""
        if self._installation_token:
            return self._installation_token
        jwt_token = self._generate_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        }
        url = f"{self.BASE_URL}/app/installations/{self.installation_id}/access_tokens"
        resp = requests.post(url, headers=headers)
        resp.raise_for_status()
        self._installation_token = resp.json()["token"]
        return self._installation_token

    def _headers(self):
        token = self._get_installation_token()
        return {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

    # --- Issues ---

    def list_issues(self, owner, repo, state="open", per_page=100):
        """Lista issues de un repositorio."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues"
        resp = requests.get(
            url,
            headers=self._headers(),
            params={"state": state, "per_page": per_page},
        )
        resp.raise_for_status()
        return resp.json()

    def get_issue(self, owner, repo, issue_number):
        """Obtiene un issue específico."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"
        resp = requests.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def create_issue(self, owner, repo, title, body="", labels=None):
        """Crea un issue en un repositorio."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues"
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        resp = requests.post(url, headers=self._headers(), json=data)
        resp.raise_for_status()
        return resp.json()

    def update_issue(self, owner, repo, issue_number, state=None, title=None, body=None):
        """Actualiza un issue (estado, título, cuerpo)."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"
        data = {}
        if state:
            data["state"] = state
        if title:
            data["title"] = title
        if body:
            data["body"] = body
        resp = requests.patch(url, headers=self._headers(), json=data)
        resp.raise_for_status()
        return resp.json()

    # --- Repos ---

    def list_installation_repos(self):
        """Lista repositorios accesibles por la instalación."""
        url = f"{self.BASE_URL}/installation/repositories"
        resp = requests.get(url, headers=self._headers(), params={"per_page": 100})
        resp.raise_for_status()
        return resp.json().get("repositories", [])

    # --- GitHub Projects v2 (GraphQL) ---

    def graphql(self, query, variables=None):
        """Ejecuta una query GraphQL contra la API de GitHub."""
        headers = self._headers()
        resp = requests.post(
            self.GRAPHQL_URL,
            headers=headers,
            json={"query": query, "variables": variables or {}},
        )
        resp.raise_for_status()
        return resp.json()

    def list_projects_v2(self, owner_login):
        """Lista los Projects v2 de un usuario u organización."""
        query = """
        query($login: String!) {
          user(login: $login) {
            projectsV2(first: 20) {
              nodes {
                id
                title
                url
                closed
              }
            }
          }
          organization(login: $login) {
            projectsV2(first: 20) {
              nodes {
                id
                title
                url
                closed
              }
            }
          }
        }
        """
        return self.graphql(query, {"login": owner_login})

    # --- Webhook verification ---

    @staticmethod
    def verify_webhook_signature(payload_body, signature_header):
        """Verifica la firma HMAC del webhook."""
        import hmac
        import hashlib

        if not signature_header:
            return False
        secret = settings.GITHUB_APP_WEBHOOK_SECRET.encode()
        expected = "sha256=" + hmac.new(
            secret, payload_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)


class GitHubOAuthClient:
    """Cliente para el flujo OAuth de GitHub (login con GitHub)."""

    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    API_URL = "https://api.github.com"

    def __init__(self):
        self.client_id = settings.GITHUB_APP_CLIENT_ID
        self.client_secret = settings.GITHUB_APP_CLIENT_SECRET

    def get_authorize_url(self, redirect_uri, state=""):
        """Construye la URL de autorización OAuth."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user repo project",
            "state": state,
        }
        from urllib.parse import urlencode

        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code(self, code, redirect_uri):
        """Intercambia el código OAuth por un access token."""
        resp = requests.post(
            self.TOKEN_URL,
            headers={"Accept": "application/json"},
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def get_user_info(self, access_token):
        """Obtiene información del usuario de GitHub."""
        resp = requests.get(
            f"{self.API_URL}/user",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        return resp.json()

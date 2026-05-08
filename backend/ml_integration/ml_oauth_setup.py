"""
Setup OAuth MercadoLibre con servidor local automático.

Uso:
    python -m backend.ml_integration.ml_oauth_setup

Requisito previo: agregar  http://localhost:8080/callback  como
Redirect URI en https://developers.mercadolibre.com.ar/apps
"""

import os
import threading
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv, set_key

load_dotenv()

APP_ID        = os.getenv("ML_APP_ID", "").strip()
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "").strip()
REDIRECT_URI  = "http://localhost:8080/callback"
AUTH_URL      = (
    f"https://auth.mercadolibre.com.ar/authorization"
    f"?response_type=code&client_id={APP_ID}&redirect_uri={REDIRECT_URI}"
)
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ENV_FILE  = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_auth_code = None
_server_done = threading.Event()


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        params = parse_qs(urlparse(self.path).query)
        code = params.get("code", [None])[0]
        error = params.get("error", [None])[0]

        if code:
            _auth_code = code
            body = b"<html><body><h2>Autorizado correctamente. Podes cerrar esta ventana.</h2></body></html>"
            self.send_response(200)
        else:
            body = f"<html><body><h2>Error: {error}</h2></body></html>".encode()
            self.send_response(400)

        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)
        _server_done.set()

    def log_message(self, *args):
        pass


def main():
    if not APP_ID or not CLIENT_SECRET:
        print("ERROR: ML_APP_ID o ML_CLIENT_SECRET no están en .env")
        return

    print("\n=== Setup OAuth MercadoLibre ===\n")
    print("IMPORTANTE: Asegurate de tener registrado este Redirect URI en tu app de ML:")
    print(f"  {REDIRECT_URI}\n")
    print("(developers.mercadolibre.com.ar → tu app → Redirect URIs)\n")

    # Iniciar servidor local en segundo plano
    server = HTTPServer(("localhost", 8080), _CallbackHandler)
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()

    print("Abriendo navegador para autorizar la app...")
    webbrowser.open(AUTH_URL)
    print(f"Si no se abre, ingresá manualmente:\n  {AUTH_URL}\n")
    print("Esperando autorización...")

    _server_done.wait(timeout=120)
    server.server_close()

    if not _auth_code:
        print("ERROR: No se recibió el código de autorización (timeout 2 min).")
        return

    print(f"Código recibido. Obteniendo tokens...")
    resp = requests.post(TOKEN_URL, data={
        "grant_type":    "authorization_code",
        "client_id":     APP_ID,
        "client_secret": CLIENT_SECRET,
        "code":          _auth_code,
        "redirect_uri":  REDIRECT_URI,
    }, timeout=10)

    if resp.status_code != 200:
        print(f"ERROR al obtener token: {resp.status_code} {resp.text}")
        return

    data = resp.json()
    set_key(ENV_FILE, "ML_ACCESS_TOKEN",  data["access_token"])
    set_key(ENV_FILE, "ML_REFRESH_TOKEN", data["refresh_token"])
    os.environ["ML_ACCESS_TOKEN"]  = data["access_token"]
    os.environ["ML_REFRESH_TOKEN"] = data["refresh_token"]

    print("\nTokens guardados en .env correctamente.")
    print(f"  ML_ACCESS_TOKEN  = {data['access_token'][:30]}...")
    print(f"\nYa podés correr el fetch de propiedades con la API oficial.")


if __name__ == "__main__":
    main()

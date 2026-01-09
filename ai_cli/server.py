"""HTTP server for cross-language access to ai-cli."""

import json
import os
import secrets
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Any

from .client import AIClient
from .exceptions import AIError, ProviderError, UnknownAliasError


class AIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for ai-cli API."""

    client: AIClient = None  # Set by run_server
    auth_token: str | None = None  # Set by run_server

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/health":
            self._send_json({"status": "ok"})
        elif self.path == "/models":
            if not self._check_auth():
                return
            models = self.client.list_models()
            self._send_json({
                "models": {
                    alias: {"provider": p, "model": m}
                    for alias, (p, m) in models.items()
                }
            })
        elif self.path == "/providers":
            if not self._check_auth():
                return
            self._send_json({
                "providers": self.client.list_providers(),
                "available": self.client.list_available_providers(),
            })
        else:
            self._send_error(404, "Not found")

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path == "/call":
            if not self._check_auth():
                return
            self._handle_call()
        else:
            self._send_error(404, "Not found")

    def _check_auth(self) -> bool:
        """Check authorization header. Returns True if authorized."""
        if self.auth_token is None:
            return True  # No auth configured

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if secrets.compare_digest(token, self.auth_token):
                return True

        self._send_error(401, "Unauthorized: invalid or missing Bearer token")
        return False

    def _handle_call(self) -> None:
        """Handle /call endpoint."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body)

            alias = data.get("alias")
            prompt = data.get("prompt")

            if alias is None or prompt is None:
                self._send_error(400, "Missing 'alias' or 'prompt' in request body")
                return

            json_mode = data.get("json_mode", False)
            yolo = data.get("yolo", False)

            result = self.client.call(alias, prompt, json_mode=json_mode, yolo=yolo)
            self._send_json({"result": result})

        except json.JSONDecodeError as e:
            self._send_error(400, f"Invalid JSON: {e}")
        except UnknownAliasError as e:
            self._send_error(404, e.message)  # Unknown alias = not found
        except ProviderError as e:
            self._send_error(502, e.message)  # Provider failed = bad gateway
        except AIError as e:
            self._send_error(400, e.message)  # Other client errors
        except Exception as e:
            self._send_error(500, str(e))  # Unexpected server error

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        """Send JSON response."""
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        """Send error response."""
        self._send_json({"error": message}, status)

    def log_message(self, format: str, *args) -> None:
        """Log HTTP requests."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def run_server(
    port: int = 8765,
    host: str = "127.0.0.1",
    token: str | None = None,
    no_auth: bool = False,
) -> None:
    """
    Start the HTTP server.

    Args:
        port: Port to listen on (default: 8765)
        host: Host to bind to (default: 127.0.0.1)
        token: Auth token for Bearer authentication. If None, auto-generates one.
        no_auth: If True, disable authentication (not recommended)
    """
    # Initialize shared client
    AIHandler.client = AIClient()

    # Setup authentication
    if no_auth:
        AIHandler.auth_token = None
        print("WARNING: Authentication disabled. Any local process can call this server.")
    else:
        # Use provided token, env var, or generate one
        AIHandler.auth_token = token or os.getenv("AI_CLI_SERVER_TOKEN") or secrets.token_urlsafe(32)

    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, AIHandler)

    print(f"ai-cli server starting on http://{host}:{port}")
    print("Endpoints:")
    print("  GET  /health    - Health check (no auth)")
    print("  GET  /models    - List available models")
    print("  GET  /providers - List providers")
    print("  POST /call      - Execute prompt")

    if AIHandler.auth_token:
        # Print to stderr to avoid log capture, and show how to use
        import sys
        print(f"\nAuth token: {AIHandler.auth_token}", file=sys.stderr)
        print("Use: Authorization: Bearer <token>", file=sys.stderr)

    print("\nPress Ctrl+C to stop")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()

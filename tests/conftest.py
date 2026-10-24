import http.server
import threading

import pytest


class Box:
    """Programmable local server: routes[path] = callable(handler) -> (status, headers, body)."""

    def __init__(self):
        self.routes = {}
        box = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                path = self.path.partition("?")[0]
                fn = box.routes.get(path)
                if fn is None:
                    status, headers, body = 404, {}, "nf"
                else:
                    status, headers, body = fn(self)
                data = body.encode()
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"


@pytest.fixture
def box():
    b = Box()
    yield b
    b.srv.shutdown()

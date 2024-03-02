from http.server import HTTPServer, SimpleHTTPRequestHandler
from .errors import DuploError
import threading
import time
import webbrowser

class TokenCallbackHandler(SimpleHTTPRequestHandler):

  def do_POST(self):
    content_length = int(self.headers['Content-Length'])
    post_data = self.rfile.read(content_length)
    
    # Send response back to client
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b'"done"')
    token = post_data.decode('utf-8')
    self.server.token = token

  def do_OPTIONS(self):
    self.send_response(200, "ok")
    self.end_headers()

  def end_headers(self):
    self.send_header('Access-Control-Allow-Origin', self.server.host)
    self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
    self.send_header('Access-Control-Allow-Headers', '*')
    self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
    return super(TokenCallbackHandler, self).end_headers()

  def log_message(self, format, *args):
    # Override to prevent printing any log messages
    pass

class TokenServer(HTTPServer):
  def __init__(self, host: str, timeout=60):
    self.token = None
    self.host = host
    self.timeout = timeout
    super().__init__(('', 0), TokenCallbackHandler, True)

  def serve_token(self):
    st = threading.Thread(target=self.serve_forever)
    wt = threading.Thread(target=self.wait_for_token)
    st.start()
    wt.start()
    wt.join(timeout=self.timeout)
    st.join()
    if not self.token:
      raise DuploError("Failed to get token", 403)
    return self.token

  def wait_for_token(self):
    i = 0
    while not self.token and i < self.timeout:
      time.sleep(1)
      i += 1
    self.shutdown()

  def open_callback(self, page: str, browser=None):
    url = f"{self.host}/{page}"
    wb = webbrowser if not browser else webbrowser.get(browser)
    wb.open(url, new=0, autoraise=True)

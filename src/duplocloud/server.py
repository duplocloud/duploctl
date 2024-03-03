from http.server import HTTPServer, SimpleHTTPRequestHandler
from .errors import DuploError
import threading
import time
import webbrowser

class TokenCallbackHandler(SimpleHTTPRequestHandler):

  def do_POST(self):
    """Do Post
    
    The post request to receive the token. The token is read from the request body and stored in the server instance.
    """
    content_length = int(self.headers['Content-Length'])
    post_data = self.rfile.read(content_length)
    
    # Send response back to client
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b'"done"')
    token = post_data.decode('utf-8')
    self.server.token = token

  def do_OPTIONS(self):
    """Do Options
    
    The preflight request for CORS.
    """
    self.send_response(200, "ok")
    self.end_headers()

  def end_headers(self):
    """End Headers
    
    Override the end headers to add the cors headers and prevent caching.
    """
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
    """TokenServer
    
    A simple HTTP server to receive a token from a callback. The bind host is always empty for localhost and the port is always 0 to get a random port. The server is started in a separate thread and the token is received in the main thread. The given host is the only host that is allowed to send a token and this is enforced in the allow origin cors header.

    Args:
      host: The host to receive the callbcack from.
      timeout: The timeout to wait for a token.

    """
    self.token = None
    self.host = host
    self.timeout = timeout
    super().__init__(('', 0), TokenCallbackHandler, True)

  def serve_token(self):
    """Serve Token
    
    Start the server and wait for a token. This is a blocking call and will wait for the token to be received from the callback or the timeout to expire. If the timeout expires, a 403 error is raised.
    """
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
    """Wait for Token
    
    Simply waits for the token to be set by the handler or the timeout to expire. 
    Ultimately the server is shutdown so no more threads are used. 
    """
    i = 0
    while not self.token and i < self.timeout:
      time.sleep(1)
      i += 1
    self.shutdown()

  def open_callback(self, page: str, browser=None):
    """Open Callback

    Opens the configured hosts callback page in the browser. 

    Args:
      page: The page to open in the browser.
      browser: The browser to use. If not specified, the default browser is used.
    """
    url = f"{self.host}/{page}"
    wb = webbrowser if not browser else webbrowser.get(browser)
    wb.open(url, new=0, autoraise=True)

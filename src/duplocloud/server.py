from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from .errors import DuploError
import threading
import time
import webbrowser
from webbrowser import Error as BrowserError
from urllib.parse import urlparse, parse_qs

HEADLESS_CALLBACK_PORT = 56789
"""Headless Callback Port

The port placed in the portal callback url when logging in headlessly. No
server ever listens on it: the browser redirect to
`http://localhost:56789/?t=<token>` is expected to fail so the token stays
visible in the address bar for the user to copy. It is a fixed, rarely used
high port so the redirect is unlikely to reach an unrelated local service.
"""


def parse_token(value: str) -> str:
  """Parse Token

  Parse a token out of what a user pasted back during a headless login. The
  paste is normally the full redirect url the browser landed on, so the token
  is read from the `t` query parameter. A bare token is accepted as is for
  portals that display the token instead of redirecting.

  Args:
    value: The pasted redirect url or a raw token.

  Returns:
    The token as a string.

  Raises:
    DuploError: If nothing was pasted or the url carries no token.
  """
  v = (value or "").strip().strip('"').strip("'")
  if not v:
    raise DuploError("No token received", 403)
  # anything that looks like a url gets the token pulled from its query,
  # including the scheme-less "localhost:56789/?t=..." browsers may show
  if "://" not in v and not v.startswith("localhost"):
    return v
  url = urlparse(v if "://" in v else f"http://{v}")
  # the token is normally in the query, but tolerate a fragment redirect
  for qs in (url.query, url.fragment):
    if qs and (token := parse_qs(qs).get("t", [None])[0]):
      return token
  raise DuploError(
    "No token found in the pasted url, expected a 't' query parameter", 403)


class TokenCallbackHandler(SimpleHTTPRequestHandler):

  def do_GET(self):
    """GET Token Handler
    
    Handles the redirect flow for a token from a redirect and GET.
    Returns a redirect back to the portal to let the user know it all worked.
    """
    # get the token from the params
    url = urlparse(self.path)
    query_components = dict(qc.split("=") for qc in url.query.split("&"))
    token = query_components.get('t', None)
    if not token:
      raise DuploError("No token received", 403)
    # store the token in the server instance
    self.server.token = token
    redirect = f"{self.server.host}/app/user/verify-token?localAppName=duploctl&success=true&localPort={self.server.server_port}"
    self.send_response(302)
    self.send_header('Location', redirect)
    self.end_headers()

      

  def do_POST(self):
    """Do Post
    
    The post request to receive the token. The token is read from the request body and stored in the server instance.
    """
    content_length = int(self.headers['Content-Length'])
    post_data = self.rfile.read(content_length)
    self.server.token = post_data.decode('utf-8')
    
    # Send response back to client
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b'"done"')

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
    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    self.send_header('Access-Control-Allow-Headers', '*')
    self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
    return super(TokenCallbackHandler, self).end_headers()

  def log_message(self, format, *args):
    # Override to prevent printing any log messages
    pass

class TokenServer(ThreadingHTTPServer):
  def __init__(self, host: str, timeout=60, port=0, bind=''):
    """TokenServer

    A simple HTTP server to receive a token from a callback. The bind host is empty for localhost and the port is 0 by default to get a random port. A specific port can be provided for relay scenarios. The server is started in a separate thread and the token is received in the main thread. The given host is the only host that is allowed to send a token and this is enforced in the allow origin cors header.

    Args:
      host: The host to receive the callbcack from.
      timeout: The timeout to wait for a token.
      port: The port to listen on. Defaults to 0 (random).
      bind: The interface to bind to. Defaults to all interfaces. Pass
        '127.0.0.1' to only accept callbacks from this machine, which is
        enough for an ssh forwarded port.

    """
    self.token = None
    self.host = host
    self.timeout = timeout
    super().__init__((bind, port), TokenCallbackHandler, True)

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

    Returns:
      True when a browser was launched, False when none could be found.

    Raises:
      DuploError: If the requested browser is not available.
    """
    url = f"{self.host}/{page}"
    try:
      wb = webbrowser if not browser else webbrowser.get(browser)
    except BrowserError as e:
      raise DuploError(
        f"Browser '{browser}' is not available, "
        "use --headless to log in without a browser", 500) from e
    return wb.open(url, new=0, autoraise=True)

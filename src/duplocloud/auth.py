from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
from pathlib import Path
import yaml
import webbrowser
from .errors import DuploError
import threading
import time

def discover_credentials(env):
  if not env.host:
    ctx = get_config_context()
    env.host = ctx.get("host", None)
    env.token = ctx.get("token", env.token)
    env.tenant = ctx.get("tenant", env.tenant)
    env.interactive = ctx.get("interactive", env.interactive)
  if not env.token and env.interactive:
    env.token = interactive_token(env.host)
  return env

def get_config_context():
  """Get Config Context
  
  Get the current context from the Duplo config.
  """
  config_path = os.environ.get("DUPLO_CONFIG", f"{Path.home()}/.duplo/config")
  if not os.path.exists(config_path): 
    raise DuploError("Duplo config not found", 500)
  conf = yaml.safe_load(open(config_path, "r"))
  ctx = conf.get("current-context", None)
  if not ctx: 
    raise DuploError("Duplo context not set, please set context to a portals name", 500)
  try:
    return [p for p in conf["contexts"] if p["name"] == ctx][0]
  except IndexError:
    raise DuploError(f"Portal '{ctx}' not found in config", 500)

def interactive_token(host: str):
  """Interactive Login
  
  Perform an interactive login to the specified host.

  Args:
    host: The host to login to.
  """
  port = 56022
  url = f"{host}/app/user/verify-token?localAppName=duploctl&localPort={port}&isAdmin=true"
  webbrowser.open(url, new=0, autoraise=True)
  with TokenServer(port, 20) as server:
    try:
      return server.token_server()
    except KeyboardInterrupt:
      server.shutdown()
      pass

class InteractiveLogin(SimpleHTTPRequestHandler):

  def do_POST(self):
    content_length = int(self.headers['Content-Length'])
    post_data = self.rfile.read(content_length)
    
    # Send response back to client
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b'done')
    token = post_data.decode('utf-8')
    self.server.token = token

  def do_OPTIONS(self):
    self.send_response(200, "ok")
    self.end_headers()

  def end_headers(self):
    self.send_header('Access-Control-Allow-Origin', '*')
    self.send_header('Access-Control-Allow-Methods', '*')
    self.send_header('Access-Control-Allow-Headers', '*')
    self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
    return super(InteractiveLogin, self).end_headers()

  def shutdown_server(self):
    self.server.shutdown()

  def log_message(self, format, *args):
    # Override to prevent printing any log messages
    pass

class TokenServer(HTTPServer):
  def __init__(self, port, timeout=20):
    self.token = None
    self.timeout = timeout
    super().__init__(('', port), InteractiveLogin, True)

  def token_server(self):
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

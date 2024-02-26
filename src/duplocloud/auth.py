from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import yaml
import webbrowser
from .errors import DuploError

class InteractiveLogin(BaseHTTPRequestHandler):
  def do_POST(self):
    content_length = int(self.headers['Content-Length'])
    post_data = self.rfile.read(content_length)
    
    # Send response back to client
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b'done')
    token = post_data.decode('utf-8')
    setattr(self.server, "token", token)

  def log_message(self, format, *args):
    # Override to prevent printing any log messages
    pass

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

def interactive_login(host: str):
  """Interactive Login
  
  Perform an interactive login to the specified host.

  Args:
    host: The host to login to.
  """
  port = 56022
  url = f"{host}/app/user/verify-token?localAppName=duploctl&localPort={port}&isAdmin=true"
  webbrowser.open(url, new=0, autoraise=True)
  with HTTPServer(('', port), InteractiveLogin) as server:
    server.timeout = 20
    try:
      server.handle_request()
      return server.token
    except KeyboardInterrupt:
      pass

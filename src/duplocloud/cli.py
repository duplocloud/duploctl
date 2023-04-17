from .client import DuploClient
import argparse
import os

def main():
  env, args = load_env()
  client = DuploClient(
    host=env.host,
    token=env.token,
    tenant_name=env.tenant,
  )
  service = client.service(env.service)
  service.exec(env.subcmd, args)

def load_env():
  """Get the environment variables for the Duplo session."""
  parser = argparse.ArgumentParser(
    prog='duplocloud-cli',
    description='Duplo Cloud CLI',
  )
  parser.add_argument('service', help='The service to run')
  parser.add_argument('subcmd', help='The subcommand to run')
  parser.add_argument('-t', '--tenant', 
                      help='The tenant to be scope into',
                      default=os.getenv('DUPLO_TENANT', 'default'))
  parser.add_argument('-H', '--host', 
                      help='The tenant to be scope into',
                      default=os.getenv('DUPLO_HOST', None))
  parser.add_argument('-p', '--token', 
                      help='The token/password to authenticate with',
                      default=os.getenv('DUPLO_TOKEN', None))
  return parser.parse_known_args()



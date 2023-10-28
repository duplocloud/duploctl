from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.commander import load_env

def main():
  env, args = load_env()
  # the qualname DuploClient.__init__
  duplo = DuploClient(**vars(env))
  service = duplo.service(env.service)
  try:
    service.exec(env.command, args)
  except DuploError as e:
    print(e)
    exit(e.code)

if __name__ == "__main__":
  main()

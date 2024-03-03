from duplocloud.client import DuploClient
from duplocloud.errors import DuploError

def main():
  try:
    duplo, args = DuploClient.from_env()
    o = duplo(*args)
    print(o)
  except DuploError as e:
    print(e)
    exit(e.code)

if __name__ == "__main__":
  main()

from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from sys import exit

def main():
  try:
    duplo, args = DuploClient.from_env()
    o = duplo(*args)
    if o:
      print(o)
  except DuploError as e:
    print(e)
    exit(e.code)
  except Exception as e:
    print(f"An unexpected error occurred: {e}")
    exit(1)

if __name__ == "__main__":
  main()

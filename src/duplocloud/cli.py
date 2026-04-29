import sys
from duplocloud.controller import DuploCtl
from duplocloud.commander import resource_help_intercept
from duplocloud.errors import DuploError

def main():
  if resource_help_intercept(sys.argv[1:]):
    return
  try:
    duplo, args = DuploCtl.from_env()
    o = duplo(*args)
    if o:
      print(o)
  except DuploError as e:
    print(e)
    sys.exit(e.code)
  except Exception as e:
    print(f"An unexpected error occurred: {e}")
    sys.exit(1)

if __name__ == "__main__":
  main()

from .types import Arg

NAME = Arg("name", 
           help='The resource name')

IMAGE = Arg("image", 
            help='The image to use')

TENANT = Arg("tenant", "-t",
             help='The tenant name')

SCHEDULE = Arg("schedule","-s", 
               help='The schedule to use')

ENABLE = Arg("enable","-y", 
              help='Enable or disable the feature',
              action='store_true',
              type=bool)

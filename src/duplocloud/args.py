import os
import argparse
from importlib.metadata import version
from .argtype import Arg, YamlAction
from .commander import available_resources

# the global args for the CLI

HOME_DIR = Arg('homedir', '--home-dir', 
            help='The home directory for duplo configurations',
            default=os.getenv('DUPLO_HOME', None))

CACHE_DIR = Arg('cachedir', '--cache-dir', 
            help='The cache directory for saved credentials.',
            default=os.getenv('DUPLO_CACHE', None))

CONFIG = Arg('configfile', '--config-file', 
            help='The path to the duploctl configuration file.',
            default=os.getenv('DUPLO_CONFIG', None))

HOST = Arg('host', '-H', 
            help='The url to specified duplo portal.',
            default=os.getenv('DUPLO_HOST', None))

TOKEN = Arg('token', '-t', 
            help='The token to authenticate with duplocloud portal api.',
            default=os.getenv('DUPLO_TOKEN', None))

TENANT = Arg("tenant", "-T",
             help='The tenant name',
             default=os.getenv('DUPLO_TENANT', None))

ARN = Arg("aws-arn", "--arn",
           help='The aws arn',
           default=None)

INTERACTIVE = Arg("interactive","-I", 
              help='Use interactive Login mode for temporary tokens. Do not use with --token.',
              type=bool,
              action='store_true')

ISADMIN = Arg("admin","--isadmin", 
              help='Request admin access when using interactive login.',
              type=bool,
              action='store_true')

CONTEXT = Arg("context", "--ctx",
              help='Use the specified context from the config file.',
              default=os.getenv('DUPLO_CONTEXT', None))

NOCACHE = Arg("no-cache","--nocache", 
              help='Do not use cache credentials.',
              type=bool,
              action='store_true')

BROWSER = Arg("web-browser","--browser", 
              help='The desired web browser to use for interactive login',
              default=os.getenv('DUPLO_BROWSER', None))

PLAN = Arg("plan", "-P",
            help='The plan name.',
            default=os.getenv('DUPLO_PLAN', None))

OUTPUT = Arg("output", "-o",
              help='The output format')

QUERY = Arg("query", "-q",
            help='The jmespath query to run on a result')

VERSION = Arg("version", "--version",
              action='version', 
              version=f"%(prog)s {version('duplocloud-client')}",
              type=bool)

# The rest are resource level args for commands
SERVICE = Arg('service', 
              help='The service to run',
              choices=available_resources())

COMMAND = Arg('command', 
             help='The subcommand to run')

# generic first positional arg for resource name
NAME = Arg("name", 
            help='The resource name')

IMAGE = Arg("image", 
            help='The image to use')

S3BUCKET = Arg("bucket",
            help='The s3 bucket to use')

S3KEY = Arg("key",
            help='The s3 key to use')

SERVICEIMAGE = Arg("serviceimage", "-S",
            help='takes two arguments, a service name and an image:tag',
            action='append',
            nargs=2,
            metavar=('service', 'image'))

SETVAR = Arg("setvar", "-V",
            help='a key and value to set as an environment variable',
            action='append',
            nargs=2,
            metavar=('key', 'value'))

STRATEGY = Arg("-strategy", "-strat",
            help='The merge strategy to use for env vars. Valid options are \"merge\" or \"replace\".  Default is merge.',
            choices=['merge', 'replace'],
            default = 'merge')

DELETEVAR = Arg("deletevar", "-D",
            action='append',
            help='a key to delete from the environment variables')

SCHEDULE = Arg("schedule","-s", 
               help='The schedule to use')

CRONSCHEDULE = Arg("cronschedule", 
               help='The schedule to use')

ENABLE = Arg("enable","-y", 
              help='Enable or disable the feature',
              type=bool,
              action='store_true')

MIN = Arg("min", "-m",
          help='The minimum number of replicas',
          type=int)

MAX = Arg("max", "-M",
          help='The maximum number of replicas',
          type=int)

BODY = Arg("file", "-f", "--cli-input",
            help='A file to read the input from',
            type=argparse.FileType('r'),
            action=YamlAction)

REPLICAS = Arg("replicas", "-r",
               help = 'Number of replicas for service',
               type = int)

WAIT = Arg("wait", "-w",
           help='Wait for the operation to complete',
           type=bool,
           action='store_true')

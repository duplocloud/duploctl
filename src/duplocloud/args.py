import argparse
import logging
from .argtype import Arg, YamlAction, JsonPatchAction, DataMapAction
from .commander import available_resources, available_formats, VERSION

# the global args for the CLI

HOME_DIR = Arg('homedir', '--home-dir', 
            help='The home directory for duplo configurations',
            env='DUPLO_HOME')
"""Home Directory

Defaults to users home directory at `$HOME/.duplo`
This is where the cli will look by default for the config and cache as well. 
"""

CACHE_DIR = Arg('cachedir', '--cache-dir', 
            help='The cache directory for saved credentials.',
            env='DUPLO_CACHE')
"""Cache Directory

Defaults to `$HOME/.duplo/cache`. This is where the cli will store the cached credentials. Sometimes you may need to delete this directory to clear out old credentials. Simply type `duploctl` and this will print where the cache is currently stored.
"""

LOGLEVEL = Arg('log-level', '--loglevel', '-L',
            help='The log level to use.',
            default='INFO',
            env='DUPLO_LOG_LEVEL',
            choices=list(logging._nameToLevel.keys()))

CONFIG = Arg('configfile', '--config-file', 
            help='The path to the duploctl configuration file.',
            env='DUPLO_CONFIG')

CONTEXT = Arg("context", "--ctx",
              help='Use the specified context from the config file.',
              env='DUPLO_CONTEXT')

HOST = Arg('host', '-H', 
            help='The url to specified duplo portal.',
            env='DUPLO_HOST')

TOKEN = Arg('token', '-t', 
            help='The token to authenticate with duplocloud portal api.',
            env='DUPLO_TOKEN')

TENANT = Arg("tenant", "-T",
             help='The tenant name',
             env='DUPLO_TENANT')
"""Tenant Name

Scopes the command into the specified tenant. In the background the TENANT_ID is discovered using this name. So if TENANT_ID is set, this is ignored. Often times this is set as an environment variable so you don't have to choose the tenant each and every command. This can also be set in the config file within a context.
"""

TENANT_ID = Arg("tenantid", "--tenant-id", "--tid",
             help='The tenant id',
             env='DUPLO_TENANT_ID')
"""Tenant ID

Scopes the command into the specified tenant. This is the internal id of the tenant. If this is set, TENANT name argument is ignored.
"""

PLAN = Arg("plan", "-P",
            help='The plan name.',
            env='DUPLO_PLAN')
"""Plan Name

This is another high level placement style argument. This is used to scope the command to a specific plan aka infrastructure. 
"""

BODY = Arg("file", "-f", "--cli-input",
            help='A file to read the input from',
            type=argparse.FileType('r'),
            action=YamlAction)
"""File Body  

This is the file path to a file with the specified resources body within. Each Resource will have it's own schema for the body. This is a yaml/json file that will be parsed and used as the body of the request. View the docs for each individual resource to see the schema for the body.
"""

DATAMAP = Arg("fromfile","--from-file", "--from-literal",
            help='A file or literal value to add to the data map',
            action=DataMapAction)

DRYRUN = Arg("dryrun", "--dry-run",
            help='Do not submit any changes to the server',
            type=bool,
            action='store_true')

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

NOCACHE = Arg("no-cache","--nocache", 
              help='Do not use cache credentials.',
              type=bool,
              action='store_true')

BROWSER = Arg("web-browser","--browser", 
              help='The desired web browser to use for interactive login',
              env='DUPLO_BROWSER',
              choices=[
                'chrome', 'chromium', 'firefox', 'safari', 'epiphany', 
                'edge', 'opera', 'konqueror', "kfm", 'w3m', 'lynx'
              ])
"""Web Browser

This is the browser of choice to use for interactive login. This is simply using the python [webbrowser](https://docs.python.org/3/library/webbrowser.html) module to open the browser. If you don't have a browser installed, you can use `w3m` or `lynx` for a text based browser.
"""

OUTPUT = Arg("output", "-o",
              help='The output format',
              default='json',
              env='DUPLO_OUTPUT',
              choices=available_formats())

QUERY = Arg("query", "-q",
            help='The jmespath query to run on a result')

PATCHES = Arg("patches", "--add", "--remove", "--copy", "--replace", "--test", "--move",
              help='The json patch to apply',
              action=JsonPatchAction)

VERSION = Arg("version", "--version",
              action='version', 
              version=f"%(prog)s {VERSION}",
              type=bool)

EXCLUDE = Arg("exclude", '--exclude',
              action='append',
              help='Exclude from the command')

# The rest are resource level args for commands
SERVICE = Arg('service', 
              help='The service to run',
              choices=available_resources())

COMMAND = Arg('command', 
             help='The subcommand to run')

# generic first positional arg for resource name
NAME = Arg("name", 
            nargs='?',
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
              action=argparse.BooleanOptionalAction)

MIN = Arg("min", "-m",
          help='The minimum number of replicas',
          type=int)

MAX = Arg("max", "-M",
          help='The maximum number of replicas',
          type=int)

REPLICAS = Arg("replicas", "-r",
               help = 'Number of replicas for service',
               type = int)

WAIT = Arg("wait", "-w",
           help='Wait for the operation to complete',
           type=bool,
           action='store_true')

SIZE = Arg("size",
           help='The instance size to use')

SAVE_SECRET = Arg("save-secret", "--save",
                 help='Save the secret to secrets manager.',
                 type=bool,
                 action='store_true')

PASSWORD = Arg("password",
                help='The password to use')

INTERVAL = Arg("interval",
                help='The monitoring interval to use',
                type=int,
                choices=[1, 5, 10, 15, 30, 60])

IMMEDIATE = Arg("immediate", "-i",
                help='Apply the change immediately',
                type=bool,
                action='store_true')

TARGET = Arg("target", "--target-name",
             help='The target name to use')

TIME = Arg("time", "--time",
           help='The time to use')

DAYS = Arg("days", 
            help='The days to use',
            type=int)

CONTENT_DIR = Arg('content', '--content-dir', 
            help='The content directory for a website.',
            default='dist',
            env='DUPLO_CONTENT')

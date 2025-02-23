from duplocloud.commander import Command, Resource
from duplocloud import args
from duplocloud.resource import DuploTenantResourceV2
from cookiecutter.main import cookiecutter
import os
import shutil
import tempfile
import boto3
import json

@Resource("ai")
class AI(DuploTenantResourceV2):
    def __init__(self, duplo):
        super().__init__(duplo)

    def __call__(self, *args):
        if not args:
            return self.help()
        command = args[0]
        if command == "tool" and len(args) > 1:
            # Pass all remaining arguments to the tool command
            return self.tool(args[1], *args[2:])
        elif command == "agent" and len(args) > 1:
            # Pass all remaining arguments to the agent command
            return self.agent(args[1], *args[2:])
        elif hasattr(self, command):
            return getattr(self, command)()
        else:
            return self.help()
    @Command()
    def tool(self, command: args.NAME = None, project_name: args.NAME = None, *tool_args):
        """AI Tool management commands"""
        if command is None:
            return self.help()
        
        # Strip leading dashes from command
        command = command.lstrip('-')
        
        method = f"tool_{command}"
        if hasattr(self, method):
            if project_name:
                return getattr(self, method)(project_name, *tool_args)
            else:
                return getattr(self, method)(*tool_args)
        else:
            raise ValueError(f"Unknown AI tool command: {command}")

    @Command()
    def agent(self, first_arg: args.NAME = None, second_arg: args.NAME = None, *agent_args):
        """Manage AI agents
        
        Usage:
            duploctl ai agent <agent_name> --add-tool <tool_name>
            duploctl ai agent --build <agent_name>
        """
        if first_arg is None:
            return self.help()

        # Check if first argument is a command (starts with --)
        if first_arg.startswith('--'):
            command = first_arg.lstrip('-').replace('-', '_')
            agent_name = second_arg
            if agent_name is None:
                raise ValueError(f"Agent name is required for command: {first_arg}")
        else:
            agent_name = first_arg
            command = second_arg.lstrip('-').replace('-', '_') if second_arg else None
            
        if command is None:
            # TODO: Show agent details when no command is provided
            return f"Showing details for agent: {agent_name} (not implemented)"
        
        method = f"agent_{command}"
        print(method)
        if hasattr(self, method):
            return getattr(self, method)(agent_name, *agent_args)
        else:
            raise ValueError(f"Unknown AI agent command: {command}. Available commands: --add-tool, --build")

    @Command()
    def agent_build(self, agent_name: args.NAME):
        """Build an AI agent
        
        Args:
            agent_name: Name of the AI agent to build
        """
        t = self.duplo.load("tenant")
        tenant = t.find()
        
        payload = {
            "AgentName": agent_name,
            "BuilderDockerImage": "938690564755.dkr.ecr.us-east-1.amazonaws.com/duplo-ai-agent-builder:latest"
        }
        
        try:
            response = self.duplo.post(f"proxy/ai-studio/v1/aistudio/agentBuilddefinitions/{tenant['TenantId']}", payload)
            return f"Successfully initiated build for agent '{agent_name}'"
        except Exception as e:
            return f"Failed to build agent: {str(e)}"

    @Command()
    def agent_add_tool(self, agent_name: args.NAME, tool_name: args.NAME = None):
        """Add a tool to an AI agent
        
        Args:
            agent_name: Name of the AI agent
            tool_name: Name of the tool to add
        """

        t = self.duplo.load("tenant")
        tenant = t.find()
        
        try:
            response = self.duplo.get(f"proxy/ai-studio/v1/aistudio/agentDefinitions/{tenant['TenantId']}/{agent_name}")
            
            agent_config = response.json()
                    
            if agent_config is None:
                raise ValueError(f"Agent with name '{agent_name}' not found")
            
            if 'toolDefinitions' not in agent_config:
                agent_config['toolDefinitions'] = []
                
            if tool_name not in agent_config['toolDefinitions']:
                agent_config['toolDefinitions'].append(tool_name)
            else:
                return f"Tool '{tool_name}' already exists in agent '{agent_name}'"

            print(f"Updating agent configuration for {agent_name}")

            response = self.duplo.put(f"proxy/ai-studio/v1/aistudio/agentDefinitions/{tenant['TenantId']}/{agent_name}", agent_config)
        
            return f"Successfully added tool '{tool_name}' to agent '{agent_name}'"
            
        except Exception as e:
            return f"Failed to update agent configuration: {str(e)}"

    @Command()
    def tool_init(self, project_name: args.NAME = None):
        """Initialize a new AI tool using cookiecutter template
        
        Args:
            project_name: Name of the AI tool project to create
        """
        if not project_name:
            raise ValueError("Project name is required. Usage: duploctl ai tool --init <project_name>")

        artifact_bucket = self.__get_artifact_bucket()
            
        template = "https://github.com/duplocloud/cookiecutter-ai-tool.git"
        try:
            # Pass the project name to cookiecutter as extra_context
            cookiecutter(
                template,
                extra_context={
                    'project_name': project_name,
                    'artifact_bucket': artifact_bucket
                },
                no_input=False
            )
            # Get the actual project directory name (it might be different from project_name due to slugification)
            project_dir = project_name.lower().replace(' ', '-')
            if os.path.exists(project_dir):
                print(f"\nSuccessfully initialized new AI tool '{project_name}' from template")
                print(f"\nTo enter the '{project_name}' project directory, run:")
                print(f"cd {project_dir}")
                
        except Exception as e:
            return f"Failed to initialize AI tool: {str(e)}"

    @Command()
    def tool_package(self):
        """Package an AI tool"""
        try:
            artifact_bucket = self.__get_artifact_bucket()
        except Exception as e:
            return f"Failed to fetch build settings: {str(e)}"

        # Create a temporary directory for the build
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create zip file name based on the current directory
            current_dir = os.path.basename(os.getcwd())
            zip_filename = f"{current_dir}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)

            try:
                # Create a zip file of the current directory
                shutil.make_archive(
                    os.path.join(temp_dir, current_dir),  # prefix for the zip file
                    'zip',                                # format
                    '.',                                  # source directory
                )
                print(f"Created build artifact: {zip_filename}")
                
                # Get AWS credentials from JIT
                jit = self.duplo.load("jit")
                aws_creds = jit.aws()

                # Upload to S3 with JIT credentials
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_creds['AccessKeyId'],
                    aws_secret_access_key=aws_creds['SecretAccessKey'],
                    aws_session_token=aws_creds['SessionToken'],
                    region_name=aws_creds.get('Region', 'us-west-2')
                )
                # Get tool name from tool.json
                tool_name = self.__get_tool_name()
                s3_key = f"{tool_name}/{zip_filename}"
                
                try:
                    s3_client.upload_file(
                        zip_path,
                        artifact_bucket,
                        s3_key
                    )
                    print(f"Successfully uploaded build artifact to s3://{artifact_bucket}/{s3_key}")
                    return "Build completed successfully"
                except Exception as e:
                    return f"Failed to upload build artifact to S3: {str(e)}"
            except Exception as e:
                return f"Failed to create build artifact: {str(e)}"

    def __get_tool_name(self) -> str:
        """Get the tool name from tool.json file

        Returns:
            str: The name of the tool

        Raises:
            Exception: If tool.json doesn't exist or is invalid
            KeyError: If Name field is missing from tool.json
        """
        try:
            with open('tool.json', 'r') as f:
                tool_config = json.loads(f.read())
                return tool_config['Name']
        except FileNotFoundError:
            raise Exception("tool.json not found in current directory")
        except json.JSONDecodeError:
            raise Exception("tool.json is not valid JSON")
        except KeyError:
            raise Exception("'Name' field not found in tool.json")

    def __get_artifact_bucket(self) -> str:
        """Get the S3 bucket for storing AI tool build artifacts

        Returns:
            str: The name of the S3 bucket

        Raises:
            Exception: If unable to fetch the build settings
        """
        # TODO: make this dynamic!!!
        settings_path = "proxy/ai-studio/v1/aistudio/settings/ea73f43c-dda3-4fb5-998d-54f262238225/default-agent-build-settings/metadata"
        response = self.duplo.get(settings_path)
        settings = response.json()
        return settings['agent-build-artifact-storage']

    @Command()
    def tool_run(self):
        """Run an AI tool"""
        # TODO: Implement tool running
        return "AI tool running - Not yet implemented"

    @Command()
    def tool_test(self):
        """Test an AI tool"""
        # TODO: Implement tool testing
        return "AI tool testing - Not yet implemented"

    @Command()
    def tool_push(self):
        """Push an AI tool to repository"""
        # TODO: Implement tool pushing
        return "AI tool pushing - Not yet implemented"

    @Command()
    def tool_create(self):
        """Create an AI tool definition from tool.json"""
        try:
            self.__get_tool_name()
            
            with open('tool.json', 'r') as f:
                tool_config = json.loads(f.read())
            
            # Get tenant ID
            t = self.duplo.load("tenant")
            tenant = t.find()
            tenant_id = tenant['TenantId']
            
            # Make the POST request to create the tool definition
            response = self.duplo.post(
                f"proxy/ai-studio/v1/aistudio/toolDefinitions/{tenant_id}",
                tool_config
            )
            
            if response.status_code == 200:
                return f"Successfully created AI tool definition for '{tool_config['Name']}'"
            else:
                return f"Failed to create AI tool definition: {response.text}"
                
        except Exception as e:
            return f"Failed to create AI tool definition: {str(e)}"

    def help(self):
        """Show AI tool help"""
        print("Available AI commands:")
        print("    tool init                        - Initialize a new AI tool from a template")
        print("    tool create                      - Create an AI tool definition from tool.json")
        print("    tool package                     - Package and upload an AI tool as a zip to S3")
        print("    tool run                         - Run an AI tool as a docker container")
        print("    tool test                        - Test an AI tool")
        print("    tool push                        - Push a build (docker image) to a registry")
        print("    agent <agent_name> --add-tool    - Add a tool to an agent")
        print("    agent <agent_name> --build       - Build an AI agent as a docker image")

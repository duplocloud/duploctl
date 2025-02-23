from duplocloud.commander import Command, Resource
from duplocloud import args
from cookiecutter.main import cookiecutter
import os

@Resource("ai")
class AI:
    def __init__(self, client):
        self.client = client

    def __call__(self, *args):
        if not args:
            return self.help()
        command = args[0]
        if command == "tool" and len(args) > 1:
            # Pass all remaining arguments to the tool command
            return self.tool(args[1], *args[2:])
        elif command == "agent":
            return self.agent()
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
    def agent(self):
        """Manage AI agents"""
        # TODO: Implement agent management
        return "AI agent management - Not yet implemented"

    @Command()
    def tool_init(self, project_name: args.NAME = None):
        """Initialize a new AI tool using cookiecutter template
        
        Args:
            project_name: Name of the AI tool project to create
        """
        if not project_name:
            raise ValueError("Project name is required. Usage: duploctl ai tool --init <project_name>")
            
        template = "https://github.com/duplocloud/cookiecutter-ai-tool.git"
        try:
            # Pass the project name to cookiecutter as extra_context
            cookiecutter(
                template,
                extra_context={
                    'project_name': project_name
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
    def tool_build(self):
        """Build an AI tool"""
        # TODO: Implement tool building
        return "AI tool building - Not yet implemented"

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

    def help(self):
        """Show AI tool help"""
        return """
Available AI commands:
    tool init   - Initialize a new AI tool
    tool build  - Build an AI tool
    tool run    - Run an AI tool
    tool test   - Test an AI tool
    tool push   - Push an AI tool to repository
    agent       - Manage AI agents
"""

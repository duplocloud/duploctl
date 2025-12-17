# Contributing

Follow these steps to be proper. There is a lot of very specific steps and automations, please read this entire document before starting. Many questions will be answered by simply getting everything setup exactly the same way in the instructions.

## Clone the Repo

Clone the repo with the wiki submodule. The wiki submodule contains the static content and templates for mkdocs.

```sh
git clone --recurse-submodules git@github.com:duplocloud/duploctl.git
```

## Environment Configuration

### Using Direnv (Local Development without Devcontainer)

If you're developing locally without using devcontainers, we recommend using [direnv](https://github.com/direnv/direnv) to automatically manage your environment variables. Direnv loads environment variables from `.envrc` and `.env` files when you `cd` into the project directory.

**Important: Environment Variable Security**
- `.envrc` - Contains **ONLY** direnv-specific commands (committed to git)
- `.env` - Contains **ALL** project variables and secrets (gitignored, never committed)
- `.env.example` - Template showing available configuration options (committed to git)

The `.envrc` file is configured to automatically load `.env` if it exists using `dotenv_if_exists`.

#### Setup Steps

1. **Install direnv** if you haven't already:
   ```sh
   # macOS
   brew install direnv
   
   # Ubuntu/Debian
   apt install direnv
   ```

2. **Hook direnv into your shell** (add to `~/.bashrc` or `~/.zshrc`):
   ```sh
   # For bash
   eval "$(direnv hook bash)"
   
   # For zsh
   eval "$(direnv hook zsh)"
   ```

3. **Create your `.env` file** from the example:
   ```sh
   cp .env.example .env
   ```

4. **Edit `.env` with your actual values**, especially:
   - `DUPLO_HOST` - Your DuploCloud portal URL
   - `DUPLO_TOKEN` - Your authentication token
   - `DUPLO_TENANT` - Your default tenant name
   - Other project-specific settings

5. **Allow direnv** to load the configuration:
   ```sh
   direnv allow
   ```

6. **Run the setup script** to install dependencies:
   ```sh
   ./scripts/setup.sh
   ```

#### The .envrc File

The `.envrc` file should **only** contain direnv stdlib commands:

```sh
# Load parent .envrc if it exists
source_up

# Setup Python 3 virtual environment (managed by direnv)
layout python3

# Add scripts directory to PATH
PATH_add ./scripts

# Load project-specific environment variables from .env
dotenv_if_exists
```

**⚠️ CRITICAL: Do NOT add secrets or tokens to `.envrc`!** This file is committed to git. All sensitive information and project-specific configuration should go in `.env`.

#### The .env File

The `.env` file contains all your project-specific environment variables and secrets. See `.env.example` for a complete list of available options. Key variables include:

- **Python Configuration**: `PY_VERSION`, `DUPLO_USE_VENV`
- **Portal Configuration**: `DUPLO_HOST`, `DUPLO_TOKEN`, `DUPLO_TENANT`, `DUPLO_INFRA`
- **Paths**: `DUPLO_HOME`, `DUPLO_CONFIG`, `DUPLO_CACHE`, `AWS_CONFIG_FILE`, `KUBECONFIG`
- **CLI Settings**: `DUPLO_OUTPUT`, `DUPLO_LOG_LEVEL`, `DUPLO_CONTEXT`
- **Secrets**: GitHub tokens, runner tokens, portal credentials

**Tip: Use 1Password CLI** to securely load tokens:
```sh
export DUPLO_TOKEN=$(op read 'op://Private/Duplo QA Token/credential')
```

### Using Devcontainer

If you're using the devcontainer (VS Code's Remote Containers), you don't need direnv. The devcontainer is configured to:

1. Automatically create a Python virtual environment (via `DUPLO_USE_VENV=1`)
2. Run `scripts/setup.sh` on container creation
3. Load environment variables if you provide a `.env` file (optional)

The devcontainer provides a consistent development environment with all dependencies pre-installed.

### Optional: Python Virtual Environment

By default, the setup script installs packages using your system Python. You can optionally create a virtual environment in `.venv` by setting:

```sh
export DUPLO_USE_VENV=1
```

This is automatically enabled in devcontainers. For local development with direnv, you can:
- Add `export DUPLO_USE_VENV=1` to your `.env` file, OR
- Use direnv's built-in `layout python3` (already in `.envrc`) which creates a venv in `.direnv/`

## Installation

Install dependencies in editable mode so you can use step through debugging. All of the optional dependencies are included within the square brackets. You can see what they all are in the [`pyproject.toml`](pyproject.toml) file.

```sh
./scripts/setup.sh
```

Or manually:

```sh
pip install --editable '.[build,test,aws,docs]'
```

Now, running `duploctl` will execute the code in your repo clone.

The unit tests are a good starting place for development.

```sh
pytest src -m unit
```

⚠️ There are also integration tests. If you run with `-m integration` or without `-m` and you have a valid `duploctl` configuration (e.g. `DUPLO_TOKEN`, etc.), these tests will create resources in your portal.

## Changelog

Make sure to take note of your changes in the changelog. This is done by updating the `CHANGELOG.md` file. Add any new details under the `## [Unreleased]` section. When a new version is published, the word `Unreleased` will be replaced with the version number and the date. The section will also be the detailed release notes under releases in Github. The checks on the PR will fail if you don't add any notes in the changelog.

See the [`version.py`](./scripts/version.py) script for more details on how the version command will inject the new version into the changelog by resetting the `Unreleased` section.

## Signed Commits

This is a public repo, one cannot simply trust that a commit came from who it says it did. To ensure the integrity of the commits, all commits must be signed. Your commits and PR will be rejected if they are not signed. Please read more about how to do this here if you do not know how: [Github Signing Commits](https://docs.github.com/en/github/authenticating-to-github/managing-commit-signature-verification/signing-commits). Ideally, if you have 1password, please follow these instructions: [1Password Signing Commits](https://blog.1password.com/git-commit-signing/).

## Building Artifacts

Build the pip package. This will cache in the build folder and the final output will be in the dist folder. This package is deployed to [pypi](https://pypi.org/project/duplocloud-client/).

```sh
python -m build
```

Building a plugin. These plugins don't necessarily need to be on pypi. They are just included alongside the release in Github. The example below shows how to build the AWS plugin. Simply replace `aws` with whatever folder name is in the [`plugins`](./plugins/) directory.

```sh
python -m build plugins/aws/ -o=dist
```

Create a single binary build for the cli using pyinstaller. These are ultimately included in the Github release so Homebrew can use them. Check out the [`scripts/installer.spec`](./scripts/installer.spec) file for the pyinstaller configuration and the [`installer.yml`](./.github/workflows/installer.yml) workflow for more details.

```sh
./scripts/installer.spec
```

Build the Homebrew formula from a tagged release. Normally only the pipeline will run this script which does properly choose the right git tag before running. This ensures the pip dependencies are correct when building the formula.

```sh
./scripts/formula.py v0.2.15
```

## Version Bump

Get the current version:

```sh
python -m setuptools_scm
```

When building the artifact the setuptools scm tool will use the a snazzy semver logic to determine version.

_ref:_ [SetupTools SCM](https://pypi.org/project/setuptools-scm/)

When Ready to publish a new version live, go to the [publish.yml](https://github.com/duplocloud/duploctl/actions/workflows/publish.yml) workflow and run the workflow manually. This will bump the version, build the artifact, and push the new version to pypi.

## Docker Image

The docker file uses a couple of stages to do a few different tasks. Mainly the official image is the runner target. The bin target is for generating multiarch binaries.

Build the main image locally for your machine using compose.

```sh
docker compose build duploctl
```

Or use bake to for a multiarch image. You just can't export images that are not your arch locally. So use compose to actually build the image locally.

```sh
docker buildx bake duploctl
```

Use buildx to build the multiarch binaries. This will output the binaries to the `dist` folder. See the Pyinstaller section above for more details on building the binaries. This runs the Pyinstaller script inside the docker container and outputs the built binaries to the local directory. This only works for linux binaries, Windows is a big maybe.

```sh
docker buildx bake duploctl-bin
```

## Building the Homebrew Formula

The homebrew formula is built from the `scripts/formula.py` script. This script will use the current git tag to build the formula.

First you need to get the frozen requirements for the formula. This is done by running the following command. This will do all local dependencies including dev only dependencies. The pipeline will make sure to only include the necessary dependencies.

```sh
pip freeze --exclude-editable > requirements.txt
```

Then generate the formula using the current git tag.

```sh
./scripts/formula.py
```

See the [`homebrew.yml`](./.github/workflows/homebrew.yml) workflow for more details on how the formula is built and pushed to the homebrew tap.

## Documentation

The wiki is a static generated website using mkdocs. All of the resource docs are pulled out from the pydoc strings in the code. The convention for docs in code is [Google style docstrings](https://google.github.io/styleguide/pyguide.html).

Here is an example of the docstring format.

```python
def my_function(param1, param2) -> dict:
    """This is a function that does something.

    Usage: CLI Usage
      ```sh
      duploctl ...
      ```

    Args:
      param1: The first parameter.
      param2: The second parameter.

    Returns:
      message: The return value.

    Raises:
        DuploError: If the value is not correct.
    """
    return {}
```

To work on the wiki you need to install the dependencies. You probably already did this if you ran the editable install command above, this includes the optional doc dependencies.

```sh
pip install --editable '.[docs]'
```

To serve the wiki locally you can run the following command. This will start a local server and watch for changes.

```sh
mkdocs serve
```

### Extending MKDocs

All of the customizations done to the doc website are done through the [`mkdocs.py`](scripts/mkdocs.py) file. One ofthe main features, there is a two phases to mkdocs now, phase 1 stages a bunch of generated  and copied markdown files, stage two generates the actual html.

*Static Files:*
All non generated and very static files go into the [`wiki`](./wiki/) submodule which is cloned into the `./wiki` folder when you clone the repo. The `hooks.py` has a hook that copies the files from the `wiki` folder into the `dist/docs` folder before final compilation.

*Themes:*
To extend the mkdocstring python theme, you can copy any of the base templates into `wiki/templates` from here https://github.com/mkdocstrings/python/tree/master/src/mkdocstrings_handlers/python/templates/material. Then simply modify the base template to do what you want.

## VSCode Setup

To be helpful as possible, all of the sweet spot configurations for VSCode are included in the `.vscode` folder. Although these files are committed they have been ignored from the working tree, so feel free to update them as you see fit and they will not be committed.

Here is how git is ignoring the files.

```sh
git update-index --skip-worktree .vscode/settings.json
```

### Step Through Debugging

Within the `.vscode/launch.json`, change the `args` to the command you want to debug, this is equivelent to running from the command line. Remember to install the project with `--editable` so you can step through the code easily.

### Tasks

All of the commands described above have been implemented as VSCode tasks in the `.vscode/tasks.json`. This goes well with the [spmeesseman.vscode-taskexplorer](https://marketplace.visualstudio.com/items?itemName=spmeesseman.vscode-taskexplorer) extension which gives you a nice little button to run the tasks.

### Devcontainer

The `.devcontainer.json` file is included for quickly spinning up a working enviornment. This is a good way to ensure that all of the dependencies are installed and the correct version of python is being used without fighting with any nuances present in your local environment.

## Self Hosted Mac Arm64 Runner

Due to limitations of GHA, there are no darwin/Arm64 machines to compile the installer for. This means you must install the self hosted runner on your own machine.

First Get a token from here: [GHA New Runner Page](https://github.com/duplocloud/duploctl/settings/actions/runners/new).
Set this variable in your `.envrc` file.

```sh
export GH_RUNNER_TOKEN="your-token-here"
```

Next you need to run the following command to make a dir and chown it so the setup-python step is happy.
[See issue here](https://github.com/actions/setup-python/blob/2f078955e4d0f34cc7a8b0108b2eb7bbe154438e/docs/advanced-usage.md#macos)

```sh
sudo mkdir -p /Users/runner /Users/runner/hostedtoolcache
sudo chown -R "$(id -un)" /Users/runner
```

Then run the following command to install the runner and activate it. Simply hit `ctrl+c` to stop the runner when it's not needed.

```sh
./scripts/runner_install.sh
```

Now that is installed, to activate it again you simply run the following command.

```sh
./actions-runner/run.sh
```

# Copyright (c) Microsoft. All rights reserved.

"""Sample subprocess-based skill script runner.
Executes file-based skill scripts as local Python subprocesses.
This is provided for demonstration purposes only.
"""

from __future__ import annotations

import subprocess
import sys

# Uncomment this filter to suppress the experimental Skills warning before
# using the sample's Skills APIs.
# import warnings
# warnings.filterwarnings("ignore", message=r"\[SKILLS\].*", category=FutureWarning)
from pathlib import Path
from typing import Any

from agent_framework import FileSkill, FileSkillScript


def subprocess_script_runner(
    skill: FileSkill, script: FileSkillScript, args: dict[str, Any] | list[str] | None = None
) -> str:
    """Run a skill script as a local Python subprocess.
    Uses ``FileSkillScript.full_path`` as the script path, converts the
    ``args`` to CLI arguments, and returns captured output.
    Args:
        skill: The file-based skill that owns the script.
        script: The file-based script to run.
        args: Optional arguments.  A list is forwarded as positional CLI
            arguments; numeric elements are converted to strings.  Passing
            a ``dict`` or any other type raises :class:`TypeError` —
            file-based scripts expect positional arguments as a JSON array.
    Returns:
        The combined stdout/stderr output, or an error message.
    Raises:
        TypeError: If ``args`` is not a list or ``None``, or if any list
            element is not a string or number.
    """
    script_path = Path(script.full_path)
    if not script_path.is_file():
        return f"Error: Script file not found: {script_path}"
    # Launch in a separate process so a skill script cannot mutate the agent's
    # Python state, and use the same interpreter/environment as the agent.
    cmd = [sys.executable, str(script_path)]
    if isinstance(args, list):
        # FileSkill scripts receive positional strings. Models often emit numbers
        # as JSON numbers (e.g. ["OPEC+", 5]), so coerce int/float to str; reject
        # other shapes instead of letting them fail obscurely inside a script.
        cli_args: list[str] = []
        for item in args:
            if isinstance(item, str):
                cli_args.append(item)
            elif isinstance(item, (int, float)) and not isinstance(item, bool):
                cli_args.append(str(item))
            else:
                raise TypeError(
                    f"File-based skill scripts only accept string or numeric CLI "
                    f"arguments but received a {type(item).__name__}."
                )
        cmd.extend(cli_args)
    elif args is not None:
        raise TypeError(
            f"Expected a list of CLI arguments but received {type(args).__name__}. "
            f"File-based skill scripts expect positional arguments as a list of strings."
        )
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            # Relative paths inside a skill should resolve against that skill,
            # not whichever directory happened to launch the agent.
            cwd=str(script_path.parent),
        )
        output = result.stdout
        # Preserve diagnostics for the model/user while keeping stdout as the
        # primary machine-readable result (the scripts emit JSON there).
        if result.stderr:
            output += f"\nStderr:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\nScript exited with code {result.returncode}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Script '{script.name}' timed out after 30 seconds."
    except OSError as e:
        return f"Error: Failed to execute script '{script.name}': {e}"

"""
Generate a Poetry-style ``pyproject.toml`` from a ``requirements.txt`` file.

Module summary
--------------
Small standalone developer utility that reads a pip ``requirements.txt``
file, translates each pinned / ranged / VCS dependency into the
``[tool.poetry.dependencies]`` syntax, and writes out a ready-to-edit
``pyproject.toml``. It exists so a project bootstrapped from a plain
requirements file can be migrated to a Poetry layout in one command.
It consumes a requirements file and produces a TOML file on disk.

Usage example
-------------
>>> #   python assets/requirements_to_toml.py \\
>>> #       --project_name my_project --requirements_file requirements.txt

Author
------
Project maintainers.
"""

from __future__ import annotations

import argparse
import logging
import os

# Module-level logger so status output is routed through the logging
# surface rather than bare prints (see CODING.md rule 6).
logger = logging.getLogger(__name__)

def read_requirements(file_path: str = 'requirements.txt') -> list[str]:
    """Read and clean a pip ``requirements.txt`` file.

    Parameters
    ----------
    file_path : str, optional
        Path to the requirements file to read (default
        ``'requirements.txt'``).

    Returns
    -------
    list[str]
        One entry per dependency line, with surrounding whitespace
        stripped and blank lines / ``#`` comment lines removed.
    """
    # Keep only meaningful lines: drop blanks and full-line comments so
    # downstream parsing never sees noise from the requirements file.
    with open(file_path) as f:
        requirements = [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]
    return requirements

def generate_pyproject_toml(
    requirements: list[str],
    project_name: str,
    description: str,
    authors: list[str],
    python_version: str,
    opensource: bool = False,
) -> str:
    """Render a Poetry-style ``pyproject.toml`` as a string.

    Parameters
    ----------
    requirements : list[str]
        Dependency lines (as returned by :func:`read_requirements`).
    project_name : str
        Value written to ``[tool.poetry].name``.
    description : str
        Short project description.
    authors : list[str]
        Author entries, each formatted as ``"Name <email>"``.
    python_version : str
        Python constraint for ``[tool.poetry.dependencies].python``
        (e.g. ``'^3.10'``).
    opensource : bool, optional
        When True, stamp a ``BSD-2-Clause`` license; otherwise leave the
        license field empty (default False).

    Returns
    -------
    str
        The full ``pyproject.toml`` content, ready to write to disk.
    """
    # An open-source project gets a permissive license stamped in; a
    # private one is left blank so it is never mislabelled as OSS.
    if opensource:
        license = 'BSD-2-Clause'
    else:
        license = ''

    return f"""
[tool.poetry]
name = "{project_name}"
version = "1.0.0"
description = "{description}"
authors = {authors}
license = "{license}"
readme = "README.md"

[tool.poetry.dependencies]
python = "{python_version}"
{format_dependencies(requirements)}

[tool.poetry.dev-dependencies]
pytest = "^6.2.5"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
"""

def format_dependencies(requirements: list[str]) -> str:
    """Translate pip requirement lines into Poetry dependency syntax.

    Parameters
    ----------
    requirements : list[str]
        Dependency lines using pip operators (``==``, ``>=``, ``<=``,
        ``@ git+``) or bare package names.

    Returns
    -------
    str
        The indented ``[tool.poetry.dependencies]`` body, one dependency
        per line, terminated by newlines.

    Notes
    -----
    Version operators are mapped to Poetry's caret/inequality style; a
    bare package with no constraint falls back to the ``"*"`` wildcard.
    """
    dependencies = ""
    # Inspect each requirement in turn and branch on the pinning operator
    # it uses — the order matters because a line may contain several
    # substrings, so the most specific constraints are tested first.
    for requirement in requirements:
        # Handle specific version constraints
        if '==' in requirement:
            package, version = requirement.split('==')
            dependencies += f'    {package.strip()} = "{version.strip()}"\n'
        elif '>=' in requirement:
            package, version = requirement.split('>=')
            dependencies += f'    {package.strip()} = ">={version.strip()}"\n'
        elif '<=' in requirement:
            package, version = requirement.split('<=')
            dependencies += f'    {package.strip()} = "<={version.strip()}"\n'
        elif '@ git+' in requirement:  # Handling Git URL dependencies
            package, u = requirement.split('@ git+')
            u = u.replace("git@github.com:", "https://github.com/")
            u = u.replace('https://https://', 'https://').strip()
            if '@' in u:
                u = u.split('@')[0]
            dependencies += f'    {package.strip()} = {{ git = "{u}", branch = "main" }}\n'
        else:  # Default to wildcard for unversioned or unspecified dependencies
            dependencies += f'    {requirement.strip()} = "*"\n'
    return dependencies

def write_pyproject_toml(content: str, file_path: str = 'pyproject.toml') -> None:
    """Write rendered TOML content to disk.

    Parameters
    ----------
    content : str
        The ``pyproject.toml`` text (as produced by
        :func:`generate_pyproject_toml`).
    file_path : str, optional
        Destination path (default ``'pyproject.toml'``). An existing file
        at this path is overwritten.

    Returns
    -------
    None
    """
    # Truncating write: this utility owns the output file, so replacing
    # any previous content is the intended behaviour.
    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate pyproject.toml from requirements.txt")

    parser.add_argument('--project_name', type=str, default='my_project', help="The name of your project")
    parser.add_argument('--description', type=str, default='A sample Python project', help="A description of your project")
    parser.add_argument('--authors', type=str, default='Your Name <you@example.com>', help="List of authors")
    parser.add_argument('--python_version', type=str, default='^3.8', help="Python version to be used in the project")
    parser.add_argument('--requirements_file', type=str, default='requirements.txt', help="Path to requirements.txt file")
    parser.add_argument('--output_file', type=str, default='pyproject.toml', help="Path to output pyproject.toml file")
    parser.add_argument("--opensource", action="store_true", help="Use this flag if your project is open source")

    args = parser.parse_args()
    authors = args.authors.split(',')
    authors = [author.strip() for author in authors]
    authors = [a for a in authors if len(a) > 0]

    python_version = args.python_version
    if not python_version.startswith('^'):
        python_version = f'^{python_version}'

    opensource = args.opensource

    # Emit user-facing status through logging so verbosity stays
    # controllable from one place instead of scattered prints.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not os.path.exists(args.requirements_file):
        logger.error("Error: %s not found.", args.requirements_file)
    else:
        requirements = read_requirements(args.requirements_file)
        toml_content = generate_pyproject_toml(
            requirements,
            project_name=args.project_name,
            description=args.description,
            authors=authors,
            python_version=python_version,
            opensource=opensource
        )
        write_pyproject_toml(toml_content, file_path=args.output_file)
        logger.info("pyproject.toml has been generated successfully at %s.", args.output_file)

import os
import argparse

def read_requirements(file_path='requirements.txt'):
    with open(file_path, 'r') as f:
        requirements = [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]
    return requirements

def generate_pyproject_toml(requirements, project_name, description, authors, python_version, opensource:bool=False):    

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

def format_dependencies(requirements):
    dependencies = ""
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

def write_pyproject_toml(content, file_path='pyproject.toml'):
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

    if not os.path.exists(args.requirements_file):
        print(f"Error: {args.requirements_file} not found.")
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
        print(f"pyproject.toml has been generated successfully at {args.output_file}.")

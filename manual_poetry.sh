#!/bin/zsh


# This is an attempt to automate the process of setting up a new Python project using Poetry.
# DO NOT RUN IT LIKE A SCRIPT, copy and paste the commands one by one in your terminal.

# Enable debug and error checking
set -x  # Print each command before executing it
set -e  # Exit the script immediately on any command failure

# Configurations
PROJECT_NAME="video-helper"
PYTHON_VERSION="3.10"
ENV="env4vh"

DEPENDENCIES="opencv-python ffmpeg-python vidgear git+https://github.com/warith-harchaoui/os-helper.git@main"
DESCRIPTION="Video Helper is a Python library that provides utility functions for processing video files. It includes features like loading, converting, extracting frames as well as working with subtitle formats."
AUTHORS="Warith Harchaoui <warith.harchaoui@gmail.com>, Mohamed Chelali <mohamed.t.chelali@gmail.com>, Bachir Zerroug <bzerroug@gmail.com>"

conda init
source ~/.zshrc

# Conda environment setup (optional, use only if Conda is required for some reason)
if conda info --envs | grep -q "^$ENV"; then
    echo "Environment $ENV already exists, removing it..."
    conda deactivate
    conda deactivate
    conda remove --name $ENV --all -y
fi


echo "Creating environment $ENV..."
conda create -y -n $ENV python=$PYTHON_VERSION
conda activate $ENV
conda install -y pip


# Poetry setup
pip install --upgrade poetry poetry2setup 


# Convert the dependencies string into an array (compatible with zsh/bash)
DEP_ARRAY=(${=DEPENDENCIES})

# Loop through each dependency and add it with poetry
for dep in "${DEP_ARRAY[@]}"; do
    echo "Adding $dep..."
    pip install "$dep"
done

yes | pip uninstall jaraco.classes
pip freeze > requirements.txt

# # replace git commit hash with @main
sed -i '' 's/@[a-f0-9]\{7,40\}/@main/g' requirements.txt

rm -f pyproject.toml poetry.lock

poetry init --name $PROJECT_NAME --description "$DESCRIPTION" --author "$AUTHORS" --python "^$PYTHON_VERSION" -n

python requirements_to_toml.py \
    --project_name "$PROJECT_NAME" \
    --description "$DESCRIPTION" \
    --authors "$AUTHORS" \
    --python_version "^$PYTHON_VERSION" \
    --requirements_file "requirements.txt" \
    --output_file "pyproject.toml"

# Initialize the Poetry project with required details
poetry install



# Generate setup.py and export requirements.txt
poetry2setup > setup.py
poetry export -f requirements.txt --output requirements.txt --without-hashes

# # replace git commit hash with @main
sed -i '' 's/@[a-f0-9]\{7,40\}/@main/g' requirements.txt


# Create environment.yml for conda users
cat <<EOL > environment.yml
name: $ENV
channels:
  - defaults
dependencies:
  - python=$PYTHON_VERSION
  - pip
  - pip:
      - -r file:requirements.txt
EOL


echo "Project setup completed successfully!"
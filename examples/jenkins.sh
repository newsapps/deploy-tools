#!/bin/bash -ex

# The most basic of Jenkins build scripts:

# Change to the current job's $WORKSPACE dir.
# This is where Jenkins keeps a copy of the project's git repo.
cd $WORKSPACE

# Create virtualenv in dir 've' in $WORKSPACE
virtualenv -q ve

# Source the newly created virtualenv
source ./ve/bin/activate

# Install the project's requirements
pip install -r requirements.txt

# Run the django_jenkins tests
python manage.py jenkins

# Django Deployment Tools

A box of tools for deploying and running Django apps on the News Application Team's rig.

# Setup

To use these tools, add this repo as a git submodule in the root of your project:

	git submodule add https://github.com/newsapps/deploy-tools.git tools

Then pull the example files in to the root of your project:

	cp -Rf tools/examples ./

Now edit the `fabfile.py` and adjust the settings for your project.

# What does it do?

Not much. It's mainly a place to put fabric commands that are used in multiple projects. It's also a place to stash scripts that we use often, but usually have to customize in some way.

`run_*_server.sh` is simple script that starts the Green Unicorn server for a particular deployment target. It expects to be installed as a `runit` service.

`run_*_worker.sh` starts a Celery worker for a particular deployment target. Also expects to be installed as a `runit` service.

`cron_*.sh` will setup the environment and run manage with whatever parameters you pass in. It's meant to be used in a crontab:

	0 * * * * /home/newsapps/sites/mynewsapp/cron_production.sh my_management_command

`fabfile.py` is where you add your fabric deployment settings. The example fabfile loads fablib, which is where all the commonly used fab commands should go.
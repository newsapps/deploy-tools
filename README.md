# Django Deployment Tools

A box of tools for deploying and running Django apps on the News Application Team's rig.

*Now with 100% more vagrancy*

# Setup

To use these tools, add this repo as a git submodule in the root of your project:

	git submodule add https://github.com/newsapps/deploy-tools.git tools

Then pull the example files in to the root of your project:

	cp -Rf tools/examples ./

Now edit the `fabfile.py` and adjust the settings for your project.

# What does it do?

Not much. It's mainly a place to put fabric commands that are used in multiple projects. It's also a place to stash scripts that we use often, but usually have to customize in some way.

`run_server.sh` is simple script that starts the Green Unicorn server for a particular deployment target. It expects to be installed as a `runit` service. This will be setup for you by Fabric.

`run_worker.sh` starts a Celery worker for a particular deployment target. Also expects to be installed as a `runit` service. This will be setup for you by Fabric.

`djcron.sh` will setup the environment and run manage with whatever parameters you pass in. It's meant to be used in a crontab:

	0 * * * * /home/newsapps/sites/mynewsapp/tools/djcron.sh deploy_target projectname my_management_command

`fabfile.py` is where you add your fabric deployment settings. The example fabfile loads fablib, which is where all the commonly used fab commands should go.

`Vagrantfile` is configuration for [Vagrant](http://vagrantup.com/). Once you have vagrant installed, run `vagrant up` in the root of your project to start a local development machine. Use the vagrant target in fab to push your application to vagrant:

  fab vagrant setup
  fab vagrant create_database 

# Vagrant

The included vagrant file will setup a fresh server with MySQL, Nginx, PostgreSQL, PostGIS, PGPool2, Memcached and Redis. It should be capable of running any Python Tribune News Application. That said, it's missing a few important things: keys for pulling private git repositories, and Amazon keys for pushing files to S3 or otherwise interacting with EC2. The Vagrant box might also have trouble running all the services at once, so you'll need to ssh in to stop any services you're not using.

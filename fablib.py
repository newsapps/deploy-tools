# Chicago Tribune News Applications fabfile
# Copying encouraged!

import os

from fabric.api import *
from fabric.contrib.console import confirm
from fabric.contrib.files import exists
from fabric.context_managers import cd
from fabric.decorators import parallel, runs_once
from fabric import colors
from contextlib import nested

env.use_ssh_config = True  # Use SSH config (~/.ssh/config)
env.use_gunicorn = True
env.use_nginx = True
env.use_django_static = True
env.django_sites = []
env.gunicorn_workers = 2
env.celery_workers = 2

SETTINGS_PROVIDERS = ["production", "staging", "vagrant", "aws"]
BRANCH_PROVIDERS = ["stable", "master", "branch"]


# Local Vagrant target
def vagrant():
    """
    Work on staging environment
    """
    env.settings = 'vagrant'
    env.hosts = ['127.0.0.1:2222']
    env.no_agent = True
    env.key_filename = '~/.vagrant.d/insecure_private_key'

    env.roledefs = {
        'app': env.hosts,
        'worker': env.hosts,
        'admin': env.hosts
    }

    env.user = 'vagrant'

    env.path = '/vagrant'
    env.env_path = '/home/%(user)s/.virtualenvs/%(project_name)s' % env
    env.repo_path = env.path

    env.s3_bucket = '%(project_name)s-vagrant' % env
    env.site_domain = '%(project_name)s.dev' % env

    env.db_root_user = 'postgres'
    env.db_root_pass = 'postgres'
    env.db_host = '192.168.33.10'

    if hasattr(env, "vagrant_settings_module"):
        env.django_settings_module = env.vagrant_settings_module
    else:
        env.django_settings_module = '%(project_name)s.vagrant_settings' % env
    print(colors.blue("--Vagrant will do all the jobs--"))


# Branches
def stable():
    """
    Work on stable branch.
    """
    print(colors.green('On stable'))
    env.branch = 'stable'


def master():
    """
    Work on development branch.
    """
    print(colors.yellow('On master'))
    env.branch = 'master'


def branch(branch_name):
    """
    Work on any specified branch.
    """
    print(colors.red('On %s' % branch_name))
    env.branch = branch_name


def rollback():
    print(colors.red('Rolling back last deploy'))
    env.branch = 'rollback'


# Commands - git
@parallel
def setup():
    """
    Setup the app on a server
    This does the bare minimum to get an app up and running. Does not do
    anything database related.
    """
    check_names()
    require('settings', provided_by=SETTINGS_PROVIDERS)
    if env.settings != "vagrant":
        require('branch', provided_by=BRANCH_PROVIDERS)

    with load_full_shell():
        # setup virtualenv
        run('mkvirtualenv %(project_name)s' % env)

    if env.settings != 'vagrant':
        # clone the project
        run('git clone %(repository_url)s %(path)s' % env)

        with cd(env.path):
            # make sure we're on the correct branch
            run('git checkout %(branch)s' % env)

            # pull down all the submodules
            run('git submodule update --init --recursive')

    # install the requirements
    install_requirements()

    # install the runit scripts for gunicorn and celery
    if env.use_gunicorn:
        install_gunicorn()

    if env.use_celery:
        install_celery()

    # install the nginx configuration
    if env.use_nginx:
        install_nginx_conf()


@parallel
@roles('app')
def install_gunicorn():
    """
    Link up and install the runit scripts for gunicorn
    """
    with settings(hide('warnings'), warn_only=True):
        # Stop all the gunicorn runit services and delete them
        sudo('sv stop %(project_name)s' % env)
        sudo('rm -Rf /etc/service/%(project_name)s' % env)
        for slug in env.django_sites:
            sudo('sv stop %s_%s' % (env.project_name, slug))
            sudo('rm -Rf /etc/service/%s_%s' % (env.project_name, slug))

    # setup the runit service directories
    sudo('mkdir /etc/service/%(project_name)s' % env)
    for slug in env.django_sites:
        sudo('mkdir /etc/service/%s_%s' % (env.project_name, slug))

    if exists('%(path)s/run_%(settings)s_server.sh' % env):
        # install a custom run_[staging|production]_server.sh script
        sudo('ln -s %(path)s/run_%(settings)s_server.sh '
             '/etc/service/%(project_name)s/run' % env)
    elif exists('%(path)s/tools/run_server.sh' % env):
        # install the generic tools run_server.sh script
        sudo('echo "#!/bin/sh\nexec %(path)s/tools/run_server.sh %(settings)s %(project_name)s %(gunicorn_workers)s" > /etc/service/%(project_name)s/run' % env)
        sudo('chmod +x /etc/service/%(project_name)s/run' % env)
        for slug in env.django_sites:
            with settings(site=slug):
                sudo('echo "#!/bin/sh\nexec %(path)s/tools/run_server.sh %(settings)s %(project_name)s %(gunicorn_workers)s %(site)s" > /etc/service/%(project_name)s_%(site)s/run' % env)
                sudo('chmod +x /etc/service/%(project_name)s_%(site)s/run' % env)

    with settings(hide('warnings'), warn_only=True):
        # make sure the log files are setup properly
        sudo('touch ~/logs/%(project_name)s.error.log' % env)
        sudo('chmod ug+rw ~/logs/%(project_name)s.error.log' % env)
        sudo('chgrp www-data ~/logs/%(project_name)s.error.log' % env)
        # start the new servers
        sudo('sv start %s' % env.project_name)
        for slug in env.django_sites:
            sudo('sv start %s_%s' % (env.project_name, slug))


@parallel
@roles('worker')
def install_celery():
    """
    Link up and install the runit script for celery
    """
    if env.use_celery:
        with settings(hide('warnings'), warn_only=True):
            sudo('sv stop %(project_name)s_worker' % env)
            sudo('rm -Rf /etc/service/%(project_name)s_worker' % env)

        # setup the runit service directories
        sudo('mkdir /etc/service/%(project_name)s_worker' % env)
        for slug in env.django_sites:
            sudo('mkdir /etc/service/%s_%s_worker' % (env.project_name, slug))

        if exists('%(path)s/run_%(settings)s_worker.sh' % env):
            # install a custom run_[staging|production]_worker.sh script
            sudo('ln -s %(path)s/run_%(settings)s_worker.sh '
                 '/etc/service/%(project_name)s_worker/run' % env)
        elif exists('%(path)s/tools/run_worker.sh' % env):
            # install the generic tools run_worker.sh script
            sudo('echo "#!/bin/sh\nexec %(path)s/tools/run_worker.sh %(settings)s %(project_name)s %(celery_workers)s" > /etc/service/%(project_name)s_worker/run' % env)
            sudo('chmod +x /etc/service/%(project_name)s_worker/run' % env)

            for slug in env.django_sites:
                with settings(site=slug):
                    sudo('echo "#!/bin/sh\nexec %(path)s/tools/run_worker.sh %(settings)s %(project_name)s %(celery_workers)s %(site)s" > /etc/service/%(project_name)s_%(site)s_worker/run' % env)
                    sudo('chmod +x /etc/service/%(project_name)s_%(site)s_worker/run' % env)

        with settings(hide('warnings'), warn_only=True):
            # make sure the log files are setup properly
            sudo('touch /home/newsapps/logs/%(project_name)s-worker.error.log' % env)
            sudo('chmod ug+rw /home/newsapps/logs/%(project_name)s-worker.error.log' % env)
            sudo('chgrp www-data /home/newsapps/logs/%(project_name)s-worker.error.log' % env)
            # start the new servers
            sudo('sv start %(project_name)s_worker' % env)
            for slug in env.django_sites:
                sudo('sv start %s_%s_worker' % (env.project_name, slug))


@parallel
@roles('app')
def install_nginx_conf():
    """
    Setup the nginx config file
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)
    with settings(hide('warnings'), warn_only=True):
        sudo('rm ~/nginx/%(project_name)s' % env)
    sudo('ln -s %(path)s/http/%(settings)s-nginx.conf ~/nginx/%(project_name)s' % env)
    sudo('service nginx reload')


@parallel
def install_requirements():
    """
    Install the required packages with pip.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    with load_full_shell(), prefix('workon %(project_name)s' % env):
        run('pip install -q -r %(path)s/requirements.txt' % env)


@parallel
def rebuild_requirements():
    """
    Remove the virtualenv and rebuild it from scratch
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    with load_full_shell():
        run('rmvirtualenv %(project_name)s' % env)
        run('mkvirtualenv %(project_name)s' % env)
        install_requirements()


@parallel
@roles('app')
def mk_cache_dir():
    """
    Creates the directory that nginx uses for caching
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)
    sudo('mkdir /mnt/nginx-cache')
    sudo('chmod ugo+rwx /mnt/nginx-cache')


# Commands - Deployment
@runs_once
def deploy():
    execute(sync)
    execute(install_requirements)
    execute(reload)
    execute(collectstatic)


@parallel
def sync():
    """
    Deploy the latest version of the site to the server. Only does git stuff,
    no application or database stuff.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)
    require('branch', provided_by=BRANCH_PROVIDERS)

    with cd(env.path):
        if env.branch != 'rollback':
            # mark our currently deployed revision so we can roll back
            run('git tag -f rollback')

            # fetch new stuff from the server
            run('git fetch')

        # make sure we're on the correct branch
        run('git checkout %(branch)s' % env)

        if env.branch != 'rollback':
            # pull updates
            run('git pull')

        # pull down all the submodules
        run('git submodule update --init --recursive')


@runs_once
def reboot():
    """
    Reload the server.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)
    if confirm("This will force services to restart and could cause errors for"
               " users. You should probably use 'reload' instead. Do you wish"
               " to continue?", default=False):
        execute(reboot_gunicorn)
        if env.use_celery:
            execute(reboot_celery)


@parallel
@roles('app')
def reboot_gunicorn():
    if env.use_gunicorn:
        print(colors.red(
            "FORCING RESTART OF GUNICORN - You should use reload_gunicorn"))
        sudo('sv restart %(project_name)s' % env)
        for site in env.django_sites:
            sudo('sv restart %s_%s' % (env.project_name, site))
        sudo('service nginx reload')


@parallel
@roles('worker')
def reboot_celery():
    """
    Force celery to restart
    """
    if env.use_celery:
        print(colors.red(
            "FORCING RESTART OF CELERY - You should use reload_celery"))
        sudo('sv restart %(project_name)s_worker' % env)
        for site in env.django_sites:
            sudo('sv restart %s_%s_worker' % (env.project_name, site))
    else:
        print(colors.red("You must set env.use_celery to True"))


@runs_once
def reload():
    """
    Gracefully reload code and configuration on the server.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)
    execute(reload_gunicorn)
    if env.use_celery:
        execute(reload_celery)


@parallel
@roles('app')
def reload_gunicorn():
    """
    Reload application code and nginx configuration
    """
    print(colors.green("Gracefully reloading gunicorn"))
    sudo('sv hup %(project_name)s' % env)
    for site in env.django_sites:
        sudo('sv hup %s_%s' % (env.project_name, site))
    sudo('service nginx reload')


@parallel
@roles('worker')
def reload_celery():
    """
    Reload celery code
    """
    if env.use_celery:
        print(colors.green("Gracefully reloading celery"))
        sudo('sv hup %(project_name)s_worker' % env)
        for site in env.django_sites:
            sudo('sv hup %s_%s_worker' % (env.project_name, site))
    else:
        print(colors.red("You must set env.use_celery to True"))


@roles('admin')
def syncdb_destroy_database():
    """
    Run syncdb after destroying the database
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    destroy_database()
    create_database()

    with cd(env.path), load_full_shell(), prefix('workon %(project_name)s' % env):
        run('DJANGO_SETTINGS_MODULE=%(django_settings_module)s ./manage.py syncdb --noinput' % env)


@roles('admin')
def create_database():
    """
    Creates the user and database for this project.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    if 'db_root_pass' not in env:
        env.db_root_pass = getpass("Database password: ")

    if env.db_type == 'postgresql':
        run('echo "CREATE ROLE %(project_name)s WITH PASSWORD \'%(database_password)s\' LOGIN CREATEDB;" | PGPASSWORD=%(db_root_pass)s psql --host=%(db_host)s --username=%(db_root_user)s postgres' % env)
        run('PGPASSWORD=%(database_password)s createdb --host=%(db_host)s --username=%(project_name)s -O %(project_name)s %(project_name)s' % env)
    else:
        run('mysqladmin --host=%(db_host)s --user=%(db_root_user)s '
            '--password=%(db_root_pass)s create %(project_name)s' % env)
        run('echo "GRANT ALL ON * TO \'%(project_name)s\'@\'%%\' '
            'IDENTIFIED BY \'%(database_password)s\';" | '
            'mysql --host=%(db_host)s --user=%(db_root_user)s '
            '--password=%(db_root_pass)s %(project_name)s' % env)


def local_create_database():
    if env.db_type == 'postgresql':
        local('echo "CREATE USER %(project_name)s WITH PASSWORD \'%(database_password)s\' CREATEUSER;" | psql postgres' % env)
        local('createdb -O %(project_name)s %(project_name)s -T template_postgis' % env)
    else:
        local('mysqladmin create %(project_name)s' % env)
        local('echo "GRANT ALL ON * TO \'%(project_name)s\'@\'localhost\' IDENTIFIED BY \'%(database_password)s\';" | mysql %(project_name)s' % env)


@roles('admin')
def destroy_database():
    """
    Destroys the user and database for this project.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    if not env.db_root_pass:
        env.db_root_pass = getpass("Database password: ")

    with settings(warn_only=True):
        if confirm("Are you sure you want to drop "
                   "the %s database?" % env.settings):
            if env.db_type == 'postgresql':
                sudo('sv stop %(project_name)s' % env)
                run('PGPASSWORD=%(database_password)s dropdb --host=%(db_host)s --username=%(project_name)s %(project_name)s' % env)
                run('PGPASSWORD=%(db_root_pass)s dropuser --host=%(db_host)s --username=%(db_root_user)s %(project_name)s' % env)
                sudo('sv start %(project_name)s' % env)
            else:
                run('mysqladmin -f --host=%(db_host)s '
                    '--user=%(db_root_user)s '
                    '--password=%(db_root_pass)s '
                    'drop %(project_name)s' % env)
                run('echo "DROP USER '
                    '\'%(project_name)s\'@\'%%\';" | '
                    'mysql --host=%(db_host)s '
                    '--user=%(db_root_user)s '
                    '--password=%(db_root_pass)s' % env)


def local_destroy_database():
    if confirm("Are you sure you want to drop the database?"):
        if env.db_type == 'postgresql':
            local('dropdb %(project_name)s' % env)
            local('dropuser %(project_name)s' % env)
        else:
            local('mysqladmin -f drop %(project_name)s' % env)
            local('echo "DROP USER \'%(project_name)s\'@\'localhost\';"| mysql' % env)


@roles('admin')
def load_data(dump_slug='dump'):
    """
    Loads a sql dump file into the database. Takes an optional parameter
    to use in the sql dump file name.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    env.dump_slug = dump_slug

    if not env.db_root_pass:
        env.db_root_pass = getpass("Database password: ")

    if env.db_type == 'postgresql':
        run("bzcat %(repo_path)s/data/%(dump_slug)s.sql.bz2 |PGPASSWORD=%(db_root_pass)s psql --host=%(db_host)s --username=%(db_root_user)s %(project_name)s" % env)
    else:
        run("bzcat %(repo_path)s/data/%(dump_slug)s.sql.bz2 "
            "|mysql --host=%(db_host)s --user=%(db_root_user)s "
            "--password=%(db_root_pass)s %(project_name)s" % env)


def local_load_data(dump_slug='dump'):
    env.dump_slug = dump_slug

    if not env.db_root_pass:
        env.db_root_pass = getpass("Database password: ")

    if env.db_type == 'postgresql':
        local("bzcat data/%(dump_slug)s.sql.bz2 |PGPASSWORD=%(db_root_pass)s psql --host=%(db_host)s --username=%(db_root_user)s %(project_name)s" % env)
    else:
        local("bzcat data/%(dump_slug)s.sql.bz2 "
            "|mysql --host=%(db_host)s --user=%(db_root_user)s "
            "--password=%(db_root_pass)s %(project_name)s" % env)


@roles('admin')
def dump_db(dump_slug='dump'):
    """
    Dump the database to a sql file in the data directory. Works
    locally or on the server. Takes an optional parameter to use in
    the sql dump file name.
    DON'T STORE DUMP FILES IN THE REPO!!
    It can end up making the repository HUGE and the files can never
    be removed from the repo history.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    env.dump_slug = dump_slug

    if not env.db_root_pass:
        env.db_root_pass = getpass("Database password: ")

    if env.db_type == 'postgresql':
        run("PGPASSWORD=%(db_root_pass)s pg_dump --host=%(db_host)s --username=%(db_root_user)s %(project_name)s |bzip2 > %(repo_path)s/data/%(dump_slug)s.sql.bz2" % env)
    else:
        run("mysqldump --host=%(db_host)s --user=%(db_root_user)s "
            "--password=%(db_root_pass)s --quick --skip-lock-tables "
            "%(project_name)s |bzip2 > "
            "%(repo_path)s/data/%(dump_slug)s.sql.bz2" % env)


def local_dump_db(dump_slug='dump'):
    env.dump_slug = dump_slug
    if env.db_type == 'postgresql':
        local("PGPASSWORD=%(db_root_pass)s pg_dump --host=%(db_host)s --username=%(db_root_user)s %(project_name)s |bzip2 > data/%(dump_slug)s.sql.bz2" % env)
    else:
        local("mysqldump --host=%(db_host)s --user=%(db_root_user)s "
            "--password=%(db_root_pass)s --quick --skip-lock-tables "
            "%(project_name)s |bzip2 > "
            "data/%(dump_slug)s.sql.bz2" % env)


@roles('admin')
def put_dump(dump_file='dump.sql.bz2'):
    """
    Upload a dump file to the chosen deployment target. Takes an optional
    parameter to use for the file name.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    env.dump_file = dump_file
    put('data/%(dump_file)s' % env,
        '%(repo_path)s/data/%(dump_file)s' % env)
    print('Put %(dump_file)s on server.\n' % env)


@roles('admin')
def get_dump(dump_file='dump.sql.bz2'):
    """
    Download a dump file from the chosen deployment target. Takes an optional
    parameter to use for the file name.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    env.dump_file = dump_file
    get('%(repo_path)s/data/%(dump_file)s' % env,
        'data/%(dump_file)s' % env)
    print('Got %(dump_file)s from the server.\n' % env)


@roles('admin')
def do_migration(migration_script):
    require('settings', provided_by=SETTINGS_PROVIDERS)

    env.migration_script = migration_script

    if not env.db_root_pass:
        env.db_root_pass = getpass("Database password: ")

    if env.db_type == 'postgresql':
        run("cat %(repo_path)s/migrations/%(migration_script)s.psql |PGPASSWORD=%(db_root_pass)s psql --host=%(db_host)s --username=%(db_root_user)s %(project_name)s" % env)
    else:
        run("cat %(repo_path)s/migrations/%(migration_script)s.mysql "
            "|mysql --host=%(db_host)s --user=%(db_root_user)s "
            "--password=%(db_root_pass)s %(project_name)s" % env)


def local_migration(migration_script):
    env.migration_script = migration_script

    if env.db_type == 'postgresql':
        local("cat migrations/%(migration_script)s.psql |psql %(project_name)s" % env)
    else:
        local("cat migrations/%(migration_script)s.mysql |mysql %(project_name)s" % env)


# Management commands
@roles('admin')
def manage(command):
    require('settings', provided_by=SETTINGS_PROVIDERS)
    with cd(env.path), load_full_shell(), prefix('workon %(project_name)s' % env):
        run('DJANGO_SETTINGS_MODULE=%s ./manage.py %s' % (env.django_settings_module, command))


@parallel
@roles('app')
def collectstatic():
    require('settings', provided_by=SETTINGS_PROVIDERS)
    with cd(env.path), load_full_shell(), prefix('workon %(project_name)s' % env):
        run('git rev-parse HEAD |cut -c 1-6 > CACHEBUSTER')
        if env.use_django_static and hasattr(env, 'django_settings_module'):
            with settings(warn_only=True):
                run('mkdir static')
            run('DJANGO_SETTINGS_MODULE=%s ./manage.py collectstatic -c --noinput' % env.django_settings_module)


# Commands - Cache
@roles('admin')
def clear_url(url):
    """
    Takes a partial url ('/story/junk-n-stuff'), and purges it from the
    Varnish cache.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    if confirm("Are you sure? This can bring the servers to their knees..."):
        for server in env.cache_servers:
            run('curl -s -I -X PURGE -H "Host: %s" http://%s%s'
                % (env.site_domain, server, url))


@roles('admin')
def clear_cache():
    """
    Connects to varnish and purges the cache for the entire site. Be careful.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    if confirm("Are you sure? This can bring the servers to their knees..."):
        for server in env.cache_servers:
            run('curl -X PURGE -H "Host: %s" http://%s/'
                % (env.site_domain, server))


@roles('app')
def clear_nginx_cache():
    """
    Connects to all the app servers and deletes the cache for this site
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    if confirm("Are you sure? This can bring the servers to their knees..."):
        sudo('rm -Rf /mnt/nginx-cache/%(project_name)s/*' % env)
        for site in env.django_sites:
            sudo('rm -Rf /mnt/nginx-cache/%s_%s/*' % (env.project_name, site))


@roles('admin')
def run_cron():
    """
    Connects to admin server and runs the cron script.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    run("%(path)s/cron_%(settings)s.sh" % env)


@parallel
@roles('app')
def weblogs():
    """
    Connect to all the servers and tail the logfiles
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    try:
        run("tail -f ~/logs/%(project_name)s.error.log" % env)
    except KeyboardInterrupt:
        pass


@parallel
@roles('worker')
def workerlogs():
    """
    Connect to all the servers and tail the logfiles
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    try:
        run("tail -f ~/logs/%(project_name)s-worker.error.log" % env)
    except KeyboardInterrupt:
        pass


# Death, destroyers of worlds
@parallel
def shiva_the_destroyer():
    """
    Remove all traces of the application from the servers. Does not
    touch databases.
    """
    require('settings', provided_by=SETTINGS_PROVIDERS)

    with settings(warn_only=True):
        # remove nginx config
        run('rm -f ~/nginx/%(project_name)s' % env)
        sudo('service nginx reload')

        # remove runit service
        sudo('sv stop %(project_name)s' % env)
        sudo('rm -Rf /etc/service/%(project_name)s' % env)

        # remove runit worker service
        if env.use_celery:
            sudo('sv stop %(project_name)s_worker' % env)
            sudo('rm -Rf /etc/service/%(project_name)s_worker' % env)

        with load_full_shell():
            run('rmvirtualenv %(project_name)s' % env)

        run('rm -Rf %(path)s' % env)


# Other utilities
def load_full_shell():
    """
    Loads the full environment, including 'workon', 'mkvirtualenv' and
    'rmvirtualenv'.
    """
    return prefix('source /etc/bash_completion')


@runs_once
def check_names():
    """
    Check that everything is named in an acceptable fashion
    """
    import re
    if re.match(r'^[a-zA-Z][a-zA-Z_0-9]+$', env.project_name) is None:
        print(colors.red("Project name '%s' contains invaild characters. It should be a valid python variable name." % env.project_name))


# Server management
def list_apps():
    run('ls -1 /etc/service/')


@parallel
@roles('app')
def stop_app():
    sudo('sv stop %s' % env.project_name)
    for site in env.django_sites:
        sudo('sv stop %s_%s' % (env.project_name, site))


@parallel
@roles('app')
def start_app():
    sudo('sv start %s' % env.project_name)
    for site in env.django_sites:
        sudo('sv start %s_%s' % (env.project_name, site))


try:
    import boto
    from boto.s3.connection import S3Connection
    from boto.s3.key import Key
    import tempfile
    import gzip
    import shutil

    ec2_conn = boto.connect_ec2()
    _s3conn = S3Connection()

    def aws(cluster):
        """
        Looks in your Amazon account for instances tagged with this Cluster.

        Also looks inside your cluster for instances tagged with Types `app`,
        `admin`, and `worker`. To put multiple types on an instance, list them
        comma-delimited.
        """
        reservations = ec2_conn.get_all_instances(
            filters={
                'tag:Cluster': cluster,
                'instance-state-name': 'running'
            })

        servers = {'all': list()}
        names = dict()
        for r in reservations:
            for i in r.instances:
                name = i.public_dns_name
                if 'User' in i.tags:
                    name = "%s@%s" % (i.tags['User'], i.public_dns_name)
                servers['all'].append(name)
                names[i.public_dns_name] = i.tags.get('Name', '')
                types = [t.strip().lower() for t in i.tags.get('Type', '').split(',')]
                for t in types:
                    if t in servers:
                        servers[t].append(name)
                    else:
                        servers[t] = [name]

        if len(servers['all']) is 0:
            raise Exception("No servers found")

        env.settings = cluster
        env.user = 'newsapps'
        #env.no_agent = True
        #env.key_filename = '~/.vagrant.d/insecure_private_key'

        env.hosts = servers['all']
        print(colors.blue("--ALL THE SERVERS--"))
        for h in env.hosts:
            print colors.white(names[h]) + ' (%s)' % h

        env.roledefs = {
            'app': servers.get('app', list()),
            'worker': servers.get('worker', list()),
            'admin': servers.get('admin', list())
        }
        print(colors.blue("--SERVERS WITH JOBS--"))
        for t, s in env.roledefs.items():
            print colors.blue(t) + ': ' + ', '.join(
                [colors.white(names[h]) for h in s])

        env.path = '/home/%(user)s/sites/%(project_name)s' % env
        env.env_path = '/home/%(user)s/.virtualenvs/%(project_name)s' % env
        env.repo_path = env.path

        env.s3_bucket = '%(project_name)s-%(settings)s' % env
        #env.site_domain = '%(project_name)s.dev' % env

        #env.db_root_user = 'postgres'
        #env.db_root_pass = 'postgres'
        #env.db_host = '192.168.33.10'

        env.django_settings_module = '%(project_name)s.%(settings)s_settings' % env

    def deploy_to_s3():
        directory = os.path.abspath("%(repo_path)s/%(project_name)s/assets" % env)
        return _deploy_to_s3(directory, env.s3_bucket)

    def _deploy_to_s3(directory, bucket):
        """
        Deploy a directory to an s3 bucket, gzipping what can be gzipped.
        Make sure you have the a boto config file, or have AWS_ACCESS_KEY_ID and
        AWS_SECRET_ACCESS_KEY environment variables.
        """
        directory = directory.rstrip('/')

        tempdir = tempfile.mkdtemp(env['project_name'])

        conn = _s3conn
        bucket = conn.get_bucket(bucket)
        existing_key_dict = dict((k.name, k) for k in bucket.list(env.project_name))
        for keyname, absolute_path in _find_file_paths(directory):
            remote_keyname = _s3_upload(keyname, absolute_path, bucket, tempdir)
            try:
                del existing_key_dict[remote_keyname]
            except:
                pass

        for key_obj in existing_key_dict.values():
            key_obj.delete()
        shutil.rmtree(tempdir, True)
        return True

    def _s3_upload(keyname, absolute_path, bucket, tempdir):
        """
        Upload a file to s3
        """
        mimetype = mimetypes.guess_type(absolute_path)
        options = {'Content-Type': mimetype[0]}

        key_parts = keyname.split('/')
        filename = key_parts.pop()

        if mimetype[0] is not None and mimetype[0].startswith('text/'):
            upload = open(absolute_path)
            options['Content-Encoding'] = 'gzip'
            temp_path = os.path.join(tempdir, filename)
            gzfile = gzip.open(temp_path, 'wb')
            gzfile.write(upload.read())
            gzfile.close()
            absolute_path = temp_path

        k = Key(bucket)
        k.key = '%s/site_media/%s' % (env.project_name, keyname)
        k.set_contents_from_filename(absolute_path, options, policy='public-read')
        return k.key

    def _find_file_paths(directory):
        """
        A generator function that recursively finds all files in the
        upload directory.
        """
        for root, dirs, files in os.walk(directory):
            rel_path = os.path.relpath(root, directory)
            for f in files:
                if rel_path == '.':
                    yield (f, os.path.join(root, f))
                else:
                    yield (os.path.join(rel_path, f), os.path.join(root, f))
except ImportError:
    def aws(cluster):
        print(colors.red("You must install boto!"))

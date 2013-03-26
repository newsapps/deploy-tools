# Chicago Tribune News Applications fabfile
# Copying encouraged!

import os

from fabric.api import *
from fabric.contrib.console import confirm
from fabric.context_managers import cd
from fabric.decorators import parallel, runs_once
import tempfile
import gzip
from boto.s3.connection import S3Connection
from boto.s3.key import Key
import shutil


# Branches
def stable():
    """
    Work on stable branch.
    """
    env.branch = 'stable'


def master():
    """
    Work on development branch.
    """
    env.branch = 'master'


def branch(branch_name):
    """
    Work on any specified branch.
    """
    env.branch = branch_name


# Commands - git
@parallel
def setup():
    require('settings', provided_by=["production", "staging"])
    require('branch', provided_by=[master, stable, branch])

    load_full_shell()
    # create the directories
    run('mkdir -p %(path)s' % env)

    # setup virtualenv
    run('mkvirtualenv %(project_name)s' % env)

    # clone the project
    run('git clone %(repository_url)s %(path)s' % env)

    with cd(env.path):
        # make sure we're on the correct branch
        run('git checkout %(branch)s' % env)

        # pull down all the submodules
        # run('git submodule update --init --recursive')

        # install the requirements
        execute(install_requirements)

    # install the runit scripts for gunicorn and celery
    execute(install_gunicorn)
    execute(install_celery)

    # install the nginx configuration
    execute(install_nginx_conf)


@parallel
@roles('app')
def install_gunicorn():
    """
    Link up and install the runit script for gunicorn
    """
    with settings(hide('warnings'), warn_only=True):
        sudo('mkdir /etc/service/%(project_name)s' % env)
        sudo('ln -s %(path)s/run_%(settings)s_server.sh '
             '/etc/service/%(project_name)s/run' % env)
        sudo('sv start %(project_name)s' % env)



@parallel
@roles('worker')
def install_celery():
    """
    Link up and install the runit script for celery
    """
    if env.use_celery:
        with settings(hide('warnings'), warn_only=True):
            sudo('mkdir /etc/service/%(project_name)s_worker' % env)
            sudo('ln -s %(path)s/run_%(settings)s_worker.sh '
                 '/etc/service/%(project_name)s_worker/run' % env)
            sudo('sv start %(project_name)s_worker' % env)


@parallel
@roles('app')
def install_nginx_conf():
    """
    Setup the nginx config file
    """
    require('settings', provided_by=[production, staging])
    with cd(env.path):
        sudo('cp http/%(settings)s-nginx.conf ~/nginx/%(project_name)s' % env)
        sudo('service nginx reload')


@parallel
def install_requirements():
    """
    Install the required packages using pip.
    """
    require('settings', provided_by=["production", "staging"])
    load_full_shell()
    with prefix('workon %(project_name)s' % env):
        run('pip install -q -r %(path)s/requirements.txt' % env)


@parallel
@roles('app')
def mk_cache_dir():
    require('settings', provided_by=["production", "staging"])
    sudo('mkdir /mnt/nginx-cache')
    sudo('chmod ugo+rwx /mnt/nginx-cache')


# Commands - Deployment
@parallel
def deploy():
    """
    Deploy the latest version of the site to the server.
    """
    require('settings', provided_by=["production", "staging"])
    require('branch', provided_by=[master, stable, branch])

    with cd(env.path):
        # fetch new stuff from the server
        run('git fetch')

        # make sure we're on the correct branch
        run('git checkout %(branch)s' % env)

        # pull updates
        run('git pull')

        # pull down all the submodules
        #run('git submodule update --init --recursive')


def reboot():
    """
    Reload the server.
    """
    require('settings', provided_by=["production", "staging"])
    execute(reboot_gunicorn)
    execute(reboot_celery)


@parallel
@roles('app')
def reboot_gunicorn():
    sudo('sv restart %(project_name)s' % env)
    sudo('service nginx reload')


@parallel
@roles('worker')
def reboot_celery():
    if env.use_celery:
        sudo('sv restart %(project_name)s_worker' % env)


@roles('admin')
def syncdb_destroy_database():
    """
    Run syncdb after destroying the database
    """
    require('settings', provided_by=["production", "staging"])

    load_full_shell()
    destroy_database()
    create_database()

    with cd(env.path):
        with prefix('workon %(project_name)s' % env):
            run('DJANGO_SETTINGS_MODULE=%(django_settings_module)s ./manage.py syncdb --noinput' % env)


@roles('admin')
def create_database():
    """
    Creates the user and database for this project.
    """
    require('settings', provided_by=["production", "staging"])

    if 'db_root_pass' not in env:
        env.db_root_pass = getpass("Database password: ")

    run('mysqladmin --host=%(db_host)s --user=%(db_root_user)s '
        '--password=%(db_root_pass)s create %(project_name)s' % env)
    run('echo "GRANT ALL ON * TO \'%(project_name)s\'@\'%%\' '
        'IDENTIFIED BY \'%(database_password)s\';" | '
        'mysql --host=%(db_host)s --user=%(db_root_user)s '
        '--password=%(db_root_pass)s %(project_name)s' % env)


@roles('admin')
def destroy_database():
    """
    Destroys the user and database for this project.
    """
    require('settings', provided_by=["production", "staging"])

    if not env.db_root_pass:
        env.db_root_pass = getpass("Database password: ")

    with settings(warn_only=True):
        if confirm("Are you sure you want to drop "
                   "the %s database?" % env.settings):
            run('mysqladmin -f --host=%(db_host)s '
                '--user=%(db_root_user)s '
                '--password=%(db_root_pass)s '
                'drop %(project_name)s' % env)
            run('echo "DROP USER '
                '\'%(project_name)s\'@\'%%\';" | '
                'mysql --host=%(db_host)s '
                '--user=%(db_root_user)s '
                '--password=%(db_root_pass)s' % env)


@roles('admin')
def load_data(dump_slug='dump'):
    """
    Loads a sql dump file into the database. Takes an optional parameter
    to use in the sql dump file name.
    """
    require('settings', provided_by=["production", "staging"])

    env.dump_slug = dump_slug

    if not env.db_root_pass:
        env.db_root_pass = getpass("Database password: ")

    run("bzcat %(repo_path)s/data/%(dump_slug)s.sql.bz2 "
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
    require('settings', provided_by=["production", "staging"])

    env.dump_slug = dump_slug

    if not env.db_root_pass:
        env.db_root_pass = getpass("Database password: ")

    run("mysqldump --host=%(db_host)s --user=%(db_root_user)s "
        "--password=%(db_root_pass)s --quick --skip-lock-tables "
        "%(project_name)s |bzip2 > "
        "%(repo_path)s/data/%(dump_slug)s.sql.bz2" % env)


@roles('admin')
def put_dump(dump_slug='dump'):
    """
    Upload a dump file to the chosen deployment target. Takes an optional
    parameter to use in the sql dump file name.
    """
    require('settings', provided_by=["production", "staging"])

    env.dump_slug = dump_slug
    put('data/%(dump_slug)s.sql.bz2' % env,
        '%(repo_path)s/data/%(dump_slug)s.sql.bz2' % env)
    print('Put %(dump_slug)s.sql.bz2 on server.\n' % env)


@roles('admin')
def get_dump(dump_slug='dump'):
    """
    Download a dump file from the chosen deployment target. Takes an optional
    parameter to use in the sql dump file name.
    """
    require('settings', provided_by=[production, staging])

    env.dump_slug = dump_slug
    get('%(repo_path)s/data/%(dump_slug)s.sql.bz2' % env,
        'data/%(dump_slug)s.sql.bz2' % env)
    print('Got %(dump_slug)s.sql.bz2 from the server.\n' % env)


@roles('admin')
def do_migration(migration_script):
    require('settings', provided_by=["production", "staging"])

    env.migration_script = migration_script

    if not env.db_root_pass:
        env.db_root_pass = getpass("Database password: ")

    run("cat %(repo_path)s/migrations/%(migration_script)s.mysql "
        "|mysql --host=%(db_host)s --user=%(db_root_user)s "
        "--password=%(db_root_pass)s %(project_name)s" % env)


# Commands - Cache
@roles('admin')
def clear_url(url):
    """
    Takes a partial url ('/story/junk-n-stuff'), and purges it from the
    Varnish cache.
    """
    require('settings', provided_by=["production", "staging"])

    if confirm("Are you sure? This can bring the servers to their knees..."):
        for server in env.cache_servers:
            run('curl -s -I -X PURGE -H "Host: %s" http://%s%s'
                % (env.site_domain, server, url))


@roles('admin')
def clear_cache():
    """
    Connects to varnish and purges the cache for the entire site. Be careful.
    """
    require('settings', provided_by=["production", "staging"])

    if confirm("Are you sure? This can bring the servers to their knees..."):
        for server in env.cache_servers:
            run('curl -X PURGE -H "Host: %s" http://%s/'
                % (env.site_domain, server))


@roles('admin')
def run_cron():
    """
    Connects to admin server and runs the cron script.
    """
    require('settings', provided_by=["production", "staging"])

    run("%(path)s/cron_%(settings)s.sh" % env)


# Death, destroyers of worlds
@parallel
def shiva_the_destroyer():
    """
    Remove all directories, databases, etc. associated with the application.
    """
    require('settings', provided_by=["production", "staging"])

    load_full_shell()
    with settings(warn_only=True):
        # remove nginx config
        run('rm ~/nginx/%(project_name)s' % env)

        # remove runit service
        sudo('sv stop %(project_name)s' % env)
        sudo('rm -Rf /etc/service/%(project_name)s' % env)

        # remove runit worker service
        if env.use_celery:
            sudo('sv stop %(project_name)s_worker' % env)
            sudo('rm -Rf /etc/service/%(project_name)s_worker' % env)

        # restart stuff
        reboot()

        run('rmvirtualenv %(project_name)s' % env)
        run('rm -Rf %(path)s' % env)


def load_full_shell():
    # Sometimes all the environment stuff doesn't get loaded.
    env.command_prefixes.append('source /etc/bash_completion')


# Other utilities
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

    conn = S3Connection()
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


def find_file_paths(directory):
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

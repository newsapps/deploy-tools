# Chicago Tribune News Applications fabfile
# Copying encouraged!

from tools.fablib import *

"""
Base configuration
"""
env.project_name = ''
env.database_password = ''
env.site_media_prefix = "static"
env.path = '/home/newsapps/sites/%(project_name)s' % env
env.env_path = '/home/newsapps/.virtualenvs/%(project_name)s' % env
env.repo_path = '%(path)s' % env
env.repository_url = ""

# Varnish cache servers to purge
env.cache_servers = []

# Setup celery
env.use_celery = False


# Environments
def production():
    """
    Work on production environment
    """
    env.settings = 'production'
    env.hosts = []

    env.roledefs = {
        'app': [],
        'worker': [],
        'admin': []
    }

    env.user = 'newsapps'

    env.s3_bucket = ''
    env.site_domain = ''

    env.db_root_user = ''
    env.db_root_pass = ''
    env.db_type = 'mysql'
    env.db_host = ''
    env.database_password = ''

    env.django_settings_module = '%(project_name)s.production_settings' % env


def staging():
    """
    Work on staging environment
    """
    env.settings = 'staging'
    env.hosts = []

    env.roledefs = {
        'app': [],
        'worker': [],
        'admin':  []
    }

    env.user = 'newsapps'

    env.s3_bucket = ''
    env.site_domain = ''

    env.db_root_user = ''
    env.db_root_pass = ''
    env.db_type = 'mysql'
    env.db_host = ''
    env.database_password = ''

    env.django_settings_module = '%(project_name)s.staging_settings' % env

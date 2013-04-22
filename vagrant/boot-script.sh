#!/bin/bash

if [ -f /var/opt/newsapps-setup-complete ]; then
  echo 'Box is already configured'
  exit
fi

USERNAME=vagrant

# Some useful bash functions

# install_pkgs $pkg_name
function install_pkg {
    echo "Installing packages $*"
    DEBIAN_FRONTEND='noninteractive' \
    apt-get -q -y -o Dpkg::Options::='--force-confnew' install \
            $*
}

# Make sure we have a locale defined
echo 'Setting locale ...'
export LANGUAGE=en_US.UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
locale-gen en_US.UTF-8
dpkg-reconfigure locales

# Set the timezone
echo "US/Central" > /etc/timezone
dpkg-reconfigure --frontend noninteractive tzdata

# update the software
echo "Updating OS..."
export DEBIAN_FRONTEND=noninteractive
apt-get -q update && apt-get -q upgrade -y

# grab some basic utilities
echo "Installing common libraries"
install_pkg build-essential python-setuptools python-dev zip \
    git-core subversion mercurial unattended-upgrades mailutils \
    libevent-dev \
    mdadm xfsprogs s3cmd python-pip python-virtualenv python-all-dev \
    virtualenvwrapper libxml2-dev libxslt-dev libgeos-dev \
    libpq-dev postgresql-client mysql-client libmysqlclient-dev \
    runit proj libfreetype6-dev libjpeg-dev zlib1g-dev \
    libgdal1-dev vim curl python-software-properties

# Get mapnik installed
add-apt-repository ppa:mapnik/v2.1.0
apt-get update
install_pkg libmapnik mapnik-utils python-mapnik

# install everything but the kitchen sink
echo "Installing servers"
install_pkg nginx memcached redis-server mysql-server postgresql-9.1-postgis

sudo -u postgres psql -d postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';" > /dev/null

echo "Creating Postgis database template"
# create postgres user
sudo -u postgres createuser -s $USERNAME

# POSTGIS setup
# Where the postgis templates should be
POSTGIS_SQL_PATH=/usr/share/postgresql/9.1/contrib/postgis-1.5

# Creating the template spatial database.
sudo -u postgres createdb -E UTF8 template_postgis

# Adding PLPGSQL language support.
#sudo -u postgres createlang -d template_postgis plpgsql

# Loading the PostGIS SQL routines
sudo -u postgres psql -d template_postgis -f $POSTGIS_SQL_PATH/postgis.sql > /dev/null
sudo -u postgres psql -d template_postgis -f $POSTGIS_SQL_PATH/spatial_ref_sys.sql > /dev/null

# Enabling users to alter spatial tables.
sudo -u postgres psql -d template_postgis -c "GRANT ALL ON geometry_columns TO PUBLIC;" > /dev/null
sudo -u postgres psql -d template_postgis -c "GRANT ALL ON spatial_ref_sys TO PUBLIC;" > /dev/null

# Allows non-superusers the ability to create from this template
sudo -u postgres psql -d postgres -c "UPDATE pg_database SET datistemplate='true' WHERE datname='template_postgis';" > /dev/null

# Make PIL build correctly
ln -s /usr/lib/x86_64-linux-gnu/libfreetype.so /usr/lib/
ln -s /usr/lib/x86_64-linux-gnu/libz.so /usr/lib/
ln -s /usr/lib/x86_64-linux-gnu/libjpeg.so /usr/lib/

echo "Setting up user environment..."

# Pull down assets
ASSET_DIR="/vagrant/tools/vagrant/assets"

cd /home/$USERNAME

# fix asset permissions
chown -Rf root:root $ASSET_DIR
chmod -Rf 755 $ASSET_DIR

# Install assets
echo "Applying overlay from tools/vagrant/assets/overlay"
rsync -r $ASSET_DIR/overlay/ /

# install scripts
echo "Installing scripts from tools/vagrant/assets/bin"
cp $ASSET_DIR/bin/* /usr/local/bin

# load private keys
echo "Installing keys from tools/vagrant/assets/*.pem"
cp $ASSET_DIR/*.pem /home/$USERNAME/.ssh/

# load authorized keys
if [ -f $ASSET_DIR/authorized_keys ]; then
  echo "Using authorized_keys from tools/vagrant/assets"
  cat $ASSET_DIR/authorized_keys >> /home/$USERNAME/.ssh/authorized_keys
fi

# load known hosts
if [ -f $ASSET_DIR/known_hosts ]; then
  echo "Using known_hosts from tools/vagrant/assets"
  cp $ASSET_DIR/known_hosts /home/$USERNAME/.ssh/known_hosts
fi

# load ssh config
if [ -f $ASSET_DIR/ssh_config ]; then
  echo "Using ssh config from tools/vagrant/assets"
  cp $ASSET_DIR/ssh_config /home/$USERNAME/.ssh/config
fi

# make sure our clocks are always on time
echo 'ntpdate ntp.ubuntu.com' > /etc/cron.daily/ntpdate
chmod +x /etc/cron.daily/ntpdate

# fix permissions in ssh folder
chmod -Rf go-rwx /home/$USERNAME/.ssh

# setup some directories
mkdir /home/$USERNAME/logs
mkdir /home/$USERNAME/sites
mkdir /home/$USERNAME/nginx

# Fix any perms that might have gotten messed up
chown -Rf $USERNAME:$USERNAME /home/$USERNAME

# Have to fix perms on postgres configs
chown -Rf postgres:postgres /etc/postgresql

# make sure our user is a member of the web group
usermod -a -G www-data $USERNAME

# Restart everything
service nginx restart
service memcached restart
service redis-server restart
service postgresql restart
service mysql restart

# Create a flag that tells this script to not run again
touch /var/opt/newsapps-setup-complete

echo 'All setup!'

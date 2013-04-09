#!/bin/sh

PROJECT=mynewsapp

GUNICORN=/home/vagrant/.virtualenvs/$PROJECT/bin/gunicorn_django
ROOT=/home/vagrant/sites/$PROJECT
PID=/var/run/$PROJECT.pid
SOCKET=/tmp/$PROJECT.sock
ERROR_LOG=/home/vagrant/logs/$PROJECT.error.log
DJANGO_SETTINGS_MODULE=$PROJECT.vagrant_settings

if [ -f $PID ]
then
    rm $PID
fi

cd $ROOT
exec $GUNICORN --bind=unix:$SOCKET --workers=2 \
    --keep-alive=0 \
    --worker-class=gevent --name=$PROJECT --pid=$PID \
    --settings=$DJANGO_SETTINGS_MODULE \
    --error-logfile=$ERROR_LOG \
    $PROJECT

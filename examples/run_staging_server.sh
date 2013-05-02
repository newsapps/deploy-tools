#!/bin/sh

PROJECT=myproject

GUNICORN=/home/newsapps/.virtualenvs/$PROJECT/bin/gunicorn
ROOT=/home/newsapps/sites/$PROJECT
PID=/var/run/$PROJECT.pid
SOCKET=/tmp/$PROJECT.sock
ERROR_LOG=/home/newsapps/logs/$PROJECT.error.log
WSGI_MODULE=$PROJECT.wsgi

export DJANGO_SETTINGS_MODULE=$PROJECT.staging_settings

if [ -f $PID ]
then
    rm $PID
fi

cd $ROOT
exec $GUNICORN --bind=unix:$SOCKET --workers=2 \
    --keep-alive=0 \
    --worker-class=gevent --name=$PROJECT --pid=$PID \
    --error-logfile=$ERROR_LOG \
    $WSGI_MODULE


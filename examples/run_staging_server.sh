#!/bin/sh

PROJECT=mynewsapp

GUNICORN=/home/newsapps/.virtualenvs/$PROJECT/bin/gunicorn_django
ROOT=/home/newsapps/sites/$PROJECT
PID=/var/run/$PROJECT.pid
SOCKET=/tmp/$PROJECT.sock
ERROR_LOG=/home/newsapps/logs/$PROJECT.error.log
DJANGO_SETTINGS_MODULE=$PROJECT.staging_settings

if [ -f $PID ]
then
    rm $PID
fi

cd $ROOT
exec $GUNICORN --bind=unix:$SOCKET --workers=5 \
    --keep-alive=0 \
    --worker-class=gevent --name=$PROJECT --pid=$PID \
    --settings=$DJANGO_SETTINGS_MODULE \
    --error-logfile=$ERROR_LOG \
    $PROJECT


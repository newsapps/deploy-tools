#!/bin/sh

PROJECT=mynewsapp

ROOT=/home/newsapps/sites/$PROJECT
VIRTUAL_ENV=/home/newsapps/.virtualenvs/$PROJECT
PID=/var/run/$PROJECT.pid
ERROR_LOG=/home/newsapps/logs/$PROJECT-worker.error.log
DJANGO_SETTINGS_MODULE=$PROJECT.production_settings

if [ -f $PID ]
then
    rm $PID
fi

cd $ROOT
source $VIRTUAL_ENV/bin/activate;
exec python ./manage.py celery worker --concurrency=2  --beat \
    --pidfile=$PID --settings=$DJANGO_SETTINGS_MODULE \
    --logfile=$ERROR_LOG

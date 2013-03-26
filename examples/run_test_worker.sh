#!/bin/sh

PROJECT=$(cd "$(dirname "$0")"; basename `pwd`)

ROOT=$(cd "$(dirname "$0")"; pwd)
PID=/tmp/$PROJECT-worker.pid
ERROR_LOG=$ROOT/$PROJECT-worker.error.log
DJANGO_SETTINGS_MODULE=$PROJECT.settings

if [ -f $PID ]
then
    rm $PID
fi

cd $ROOT
exec python ./manage.py celery worker --concurrency=2  --beat \
    --pidfile=$PID --settings=$DJANGO_SETTINGS_MODULE \
    --logfile=$ERROR_LOG


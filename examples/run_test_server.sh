#!/bin/sh

PROJECT=$(cd "$(dirname "$0")"; basename `pwd`)

GUNICORN=`which gunicorn`
ROOT=$(cd "$(dirname "$0")"; pwd)
PID=/tmp/$PROJECT.pid
SOCKET=/tmp/$PROJECT.sock
ERROR_LOG=$ROOT/$PROJECT.error.log
WSGI_MODULE=$PROJECT.wsgi

export DJANGO_SETTINGS_MODULE=$PROJECT.settings

if [ -f $PID ]
then
    rm $PID
fi

cd $ROOT
exec $GUNICORN --bind=unix:$SOCKET --workers=5 \
    --keep-alive=0 \
    --worker-class=gevent --name=$PROJECT --pid=$PID \
    $WSGI_MODULE


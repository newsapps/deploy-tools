#!/bin/sh
EXPECTED_ARGS=2
E_BADARGS=65

if [ $# -ne $EXPECTED_ARGS ]
then
  echo "Usage: `basename $0` <deploy target> <projectname> [num workers]"
  echo "Run a gunicorn server for the app in /home/newsapps/sites/projectname."
  exit $E_BADARGS
fi

TARGET=$1
PROJECT=$2
WORKERS=${3:-'2'}

ROOT=/home/newsapps/sites/$PROJECT
GUNICORN=/home/newsapps/.virtualenvs/$PROJECT/bin/gunicorn
PID=/var/run/$PROJECT.pid
SOCKET=/tmp/$PROJECT.sock
ERROR_LOG=/home/newsapps/logs/$PROJECT.error.log
SECRETS=/home/newsapps/sites/secrets/${TARGET}_secrets.sh

if [ -f $ROOT/application.py ]
then
  WSGI_MODULE=application
else
  if [ -d $ROOT/$PROJECT/configs ]
  then
    export DJANGO_SETTINGS_MODULE=$PROJECT.configs.$TARGET.settings
    WSGI_MODULE=$PROJECT.configs.$TARGET.wsgi
    PYTHONPATH=$ROOT/$PROJECT:$ROOT
  else
    export DJANGO_SETTINGS_MODULE=$PROJECT.${TARGET}_settings
    WSGI_MODULE=$PROJECT.wsgi
  fi
fi

if [ -f $PID ]
then
  rm $PID
fi

if [ -f $SECRETS ]
then
  . $SECRETS
fi

cd $ROOT
exec $GUNICORN --bind=unix:$SOCKET --workers=$WORKERS \
    --keep-alive=0 --max-requests=1000 --user=www-data \
    --group=www-data --name=$PROJECT \
    --worker-class=gevent --pid=$PID --error-logfile=$ERROR_LOG \
    $WSGI_MODULE


#!/bin/sh
EXPECTED_ARGS=2
E_BADARGS=65

if [ $# -lt $EXPECTED_ARGS ]
then
  echo "Usage: `basename $0` <deploy target> <projectname> [num workers]"
  echo "Run a gunicorn server for the app in /home/newsapps/sites/projectname."
  exit $E_BADARGS
fi

TARGET=$1
PROJECT=$2
WORKERS=${3:-'2'}

USE_ACCOUNT=www-data
ROOT=/home/newsapps/sites/$PROJECT
GUNICORN=/home/newsapps/.virtualenvs/$PROJECT/bin/gunicorn
SOCKET=/tmp/$PROJECT.sock
ERROR_LOG=/home/newsapps/logs/$PROJECT.error.log
SECRETS=/home/newsapps/sites/secrets/${TARGET}_secrets.sh

export DEPLOYMENT_TARGET=$TARGET

if [ -f $ROOT/application.py ]
then
  if [ -f $ROOT/$PROJECT/${TARGET}_config.py ]
  then
    export CONFIG_MODULE=${PROJECT}.${TARGET}_config
  elif [ -f $ROOT/${TARGET}_config.py ]
  then
    export CONFIG_MODULE=${TARGET}_config
  fi
  WSGI_MODULE=application
else
  if [ -d $ROOT/$PROJECT/configs ]
  then
    export DJANGO_SETTINGS_MODULE=$PROJECT.configs.$TARGET.settings
    export PYTHONPATH=$ROOT/$PROJECT:$ROOT
    WSGI_MODULE=$PROJECT.configs.$TARGET.wsgi
  else
    export DJANGO_SETTINGS_MODULE=$PROJECT.${TARGET}_settings
    WSGI_MODULE=$PROJECT.wsgi
  fi
fi

if [ -f $SECRETS ]
then
  . $SECRETS
fi

cd $ROOT
exec $GUNICORN --bind=unix:$SOCKET --workers=$WORKERS \
    --keep-alive=0 --max-requests=1000 --user=www-data \
    --group=$USE_ACCOUNT --name=$PROJECT \
    --worker-class=gevent --error-logfile=$ERROR_LOG \
    $WSGI_MODULE


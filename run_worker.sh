#!/bin/sh
EXPECTED_ARGS=2
E_BADARGS=65

if [ $# -lt $EXPECTED_ARGS ]
then
  echo "Usage: `basename $0` <deploy target> <projectname> [num workers]"
  echo "Run a celery server for the app in /home/newsapps/sites/projectname."
  exit $E_BADARGS
fi

TARGET=$1
PROJECT=$2
WORKERS=${3:-'2'}
SITE=${4:-''}

USE_ACCOUNT=www-data
ROOT=/home/newsapps/sites/$PROJECT
VIRTUAL_ENV=/home/newsapps/.virtualenvs/$PROJECT
ERROR_LOG=/home/newsapps/logs/$PROJECT.error.log
WORKER_ERROR_LOG=/home/newsapps/logs/$PROJECT-worker.error.log
SECRETS=/home/newsapps/sites/secrets/${TARGET}_secrets.sh
HOSTNAME=${PROJECT}.`hostname`

if [ -f $ROOT/application.py ]
then
  CELERY="celery worker --hostname=${HOSTNAME}"
else
  if [ -d $ROOT/$PROJECT/settings ]
  then
    if [ -z "$SITE" ]
    then
      export DJANGO_SETTINGS_MODULE=$PROJECT.settings.${TARGET}
    else
      export DJANGO_SETTINGS_MODULE=$PROJECT.settings.${SITE}_${TARGET}
      HOSTNAME=${SITE}.${HOSTNAME}
    fi
  else
    export DJANGO_SETTINGS_MODULE=$PROJECT.${TARGET}_settings
  fi
  CELERY="$ROOT/manage.py celery worker --hostname=${HOSTNAME}"
fi

if [ -f $SECRETS ]
then
  . $SECRETS
fi

. $VIRTUAL_ENV/bin/activate
cd $ROOT
exec chpst -u $USE_ACCOUNT $CELERY \
    --concurrency=$WORKERS --pool=gevent --logfile=$WORKER_ERROR_LOG \
    --events --maxtasksperchild=100

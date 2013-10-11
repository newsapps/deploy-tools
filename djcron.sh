#!/bin/bash
EXPECTED_ARGS=2
E_BADARGS=65

if [ $# -lt $EXPECTED_ARGS ]
then
  echo "Usage: `basename $0` <deploy target> <projectname>"
  echo "Run Django management command for the app in /home/newsapps/sites/projectname."
  exit $E_BADARGS
fi

TARGET=$1
PROJECT=$2

source /home/newsapps/.virtualenvs/$PROJECT/bin/activate;
export DJANGO_SETTINGS_MODULE=$PROJECT.${TARGET}_settings;
/home/newsapps/sites/$PROJECT/manage.py ${@:3};

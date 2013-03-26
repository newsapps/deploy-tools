#!/bin/bash

PROJECT=ugc

source /home/newsapps/.virtualenvs/$PROJECT/bin/activate;
export DJANGO_SETTINGS_MODULE=$PROJECT.production_settings;
/home/newsapps/sites/$PROJECT/manage.py $@;

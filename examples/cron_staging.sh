#!/bin/bash

PROJECT=ugc

source /home/newsapps/.virtualenvs/$PROJECT/bin/activate;
export DJANGO_SETTINGS_MODULE=$PROJECT.staging_settings;
/home/newsapps/sites/$PROJECT/manage.py $@;


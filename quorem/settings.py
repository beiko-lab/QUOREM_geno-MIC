"""
Django settings for quorem project.

Generated by 'django-admin startproject' using Django 2.1.3.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
from distutils.version import LooseVersion
from django.utils.version import get_version

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '4pmq)x=1c+b8*am8ok9xc!-tt-3=_1&rjp!i^o-bvebehf8m3y'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['192.168.1.142','47.54.56.77', 'localhost', '127.0.0.1']

# Django-jinja2-knockout'd packages
DJK_APPS = ['quorem', 'db']

# Application definition

INSTALLED_APPS = [
    'accounts',
    'landingpage',
    'django_tables2',
    #postgres, needed for search functionality
    'django.contrib.postgres',
    #'import_export',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_jinja',
    'django_jinja.contrib._humanize',
    'django_jinja_knockout',
    'djk_ui',

] + DJK_APPS

DJK_MIDDLEWARE = 'quorem.middleware.ContextMiddleware'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
if LooseVersion(get_version()) >= LooseVersion('1.11'):
    MIDDLEWARE.append(DJK_MIDDLEWARE)
else:
    MIDDLEWARE_CLASSES = MIDDLEWARE
    MIDDLEWARE.extend([
        'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
        DJK_MIDDLEWARE,
    ])

ROOT_URLCONF = 'quorem.urls'

CELERY_BROKER_URL = 'redis://127.0.0.1:6379'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

TEMPLATES = [
        {
          "BACKEND": "django_jinja.backend.Jinja2",
          "APP_DIRS": True,
          "OPTIONS": {
            "match_extension": ".htm",
            "app_dirname": "jinja2",
            'context_processors': [
                'django.template.context_processors.i18n',
                'django_jinja_knockout.context_processors.template_context_processor'
            ],
            'environment': 'quorem.jinja2.environment',
            
          },
        },
        { 'BACKEND': 'django.template.backends.django.DjangoTemplates',
          'DIRS': [],
          'APP_DIRS': True,
          'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
          },
        },
]

WSGI_APPLICATION = 'quorem.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'quoremtest',
        'USER': 'alex',
        'PASSWORD': '15fdnigp',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

# this should be fine if we are not letting anyone upload staticfiles.
# if not, we need to configure aws s3
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

'''
STATICFILES_DIRS = [
    "vendors",
]
'''

AUTH_USER_MODEL = 'accounts.User'

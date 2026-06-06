import os
from pathlib import Path
from decouple import config
import environ


BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# ==============================================================================
# CORE SETTINGS USING ENV VARIABLES
# ==============================================================================
SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=True)

# DATABASE CONFIGURATION
DATABASES = {
    'default': env.db('DATABASE_URL', default=f"postgresql://{env('DB_USER')}:{env('DB_PASSWORD')}@{env('DB_HOST')}:{env('DB_PORT')}/{env('DB_NAME')}")
}


# EMAIL CONFIGURATION
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = env('EMAIL_HOST_USER')

# Redirect endpoints
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'landing_page'
LOGOUT_REDIRECT_URL = 'landing_page'

# Application definition
INSTALLED_APPS = [
  'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites', 
    'Accounts', 
    'adminpanel',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google', 
]
# Required for django.contrib.sites to know which database site domain to target
SITE_ID = 1



# Custom user model configuration (Single entry point)
AUTH_USER_MODEL = 'Accounts.CustomUser'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'wheelverse.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')], # Template directory track cheyyan
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'wheelverse.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'wheelverse',
        'USER': 'postgres',
        'PASSWORD': '2255',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator' },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator' },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
    # `allauth` specific authentication methods, such as login by email
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth login methods (modern syntax — replaces deprecated ACCOUNT_AUTHENTICATION_METHOD)
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_EMAIL_VERIFICATION = 'none'

# Skip the redundant "Are you sure you want to sign in?" page
SOCIALACCOUNT_LOGIN_ON_GET = True

# Match these string names with what you used in your urls.py routing blocks
LOGIN_REDIRECT_URL = 'landing_page' 
LOGOUT_REDIRECT_URL = 'login'

# Automatically creates a username based on the user's email prefix and skips the intermediate form
SOCIALACCOUNT_AUTO_SIGNUP = True

# Allauth signup fields — username is optional so Google can auto-signup without prompting
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username', 'password1*', 'password2*']
ACCOUNT_UNIQUE_EMAIL = True

# Automatically link social accounts to existing local accounts with the same email
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Custom adapter: auto-generates a unique username from Google email/name
SOCIALACCOUNT_ADAPTER = 'Accounts.adapter.WheelVerseSocialAccountAdapter'

# Google OAuth2 provider configuration
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
        'FETCH_USERINFO': True,
    }
}


MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


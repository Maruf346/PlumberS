from pathlib import Path
import os
from datetime import timedelta
# import firebase_admin
# from firebase_admin import credentials
from dotenv import load_dotenv
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG') == 'True'

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'daphne',
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third-party apps
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    'django_filters',
    'django_redis',
    'phonenumber_field',
    'django_ckeditor_5',
    'channels',
    'django_celery_beat',
    
    # Local apps
    'user',
    'api',
    'certificates',
    'supports',
    'notifications',
    'clients',
    'safety_forms',
    'fleets',
    'fleet_inspections',
    'jobs',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.sqlite3')

if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db_volume' / 'db.sqlite3',
            # Stored in the named Docker volume → survives image rebuilds
        }
    }
else:
    # Production (PostgreSQL on AWS RDS) — just flip env vars, no code change needed
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }


# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/1', # conn url, [/1 -> Redis db no. 1]
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'autointel',   # Adds a prefix to every cache key.
        'TIMEOUT': 300,  # Default cache expiry time = 300s (5 mins).
    }
}


# CORS configs
CORS_ALLOW_ALL_ORIGINS = True


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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


AUTH_USER_MODEL = 'user.User'


# # Security Settings (Data Encryption)
# SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT')
# SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE')
# CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE')


SITE_ID = 1
FRONTEND_LOGIN_ERROR_URL = os.getenv('FRONTEND_LOGIN_ERROR_URL')
FRONTEND_LOGIN_SUCCESS_URL = os.getenv('FRONTEND_LOGIN_SUCCESS_URL')

# Google OAuth2 Settings
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI')
 # for mobile
GOOGLE_WEB_CLIENT_ID = os.getenv('GOOGLE_WEB_CLIENT_ID')

if DEBUG:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    

# Apple OAuth
# APPLE_TEAM_ID = os.getenv('APPLE_TEAM_ID')
# APPLE_PRIVATE_KEY = os.getenv('APPLE_PRIVATE_KEY')
# APPLE_KEY_ID = os.getenv('APPLE_KEY_ID')
APPLE_CLIENT_ID = os.getenv('APPLE_CLIENT_ID')
# APPLE_REDIRECT_URI = os.getenv('APPLE_REDIRECT_URI')


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

# Static and media files settings
STATIC_URL = 'static/'
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# Application URLs
BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:8000/')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')


# Rest Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        #'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
        'rest_framework.filters.SearchFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 5,
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    
}


# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Adelaide Plumbing and Gasfitting API',
    'DESCRIPTION': "API for Adelaide Plumbing and Gasfitting",
    'VERSION': '1.0.1',
    'TERMS_OF_SERVICE': 'https://www.google.com/policies/terms/',
    'CONTACT': {'email': 'maruf.bshs@gmail.com'},
    'LICENSE': {'name': 'BSD License'},
    'SERVE_INCLUDE_SCHEMA': False,
    
    # Postman friendly settings
    'COMPONENT_SPLIT_REQUEST': True,
    #'POSTMAN_ENABLED': True,
    'SORT_OPERATIONS': False,
    
}


# Jazzmin settings
JAZZMIN_SETTINGS = {
    "site_title": "PlumberS Admin",
    "site_header": "PlumberS",
    "site_brand": "PlumberS",
    "welcome_sign": "Welcome to the PlumberS Admin Panel",
    "copyright": "PlumberS © 2026",
    "user_avatar": None,
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
    },
    "default_icon_parents": "fas fa-chevron-right",
    "default_icon_children": "fas fa-circle",
}


JAZZMIN_UI_TWEAKS = {
    "theme": "lux",
    "dark_mode_theme": "darkly",
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_color": "primary",
    "accent": "primary",
    "navbar": "navbar-dark bg-primary",
    "no_navbar_border": False,
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
   
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
   
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
   
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
   
    'JTI_CLAIM': 'jti',
}


# Celery Configs
CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'  # message broker
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/0' 
CELERY_ACCEPT_CONTENT = ['json']  # Celery will only accept tasks serialized as JSON.
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True  # Celery tracks when a task starts executing.
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes


# Email Configs (MailHog for development)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '1025'))  # MailHog default port
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False') == 'True' # For production → TLS is often True.
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False') == 'True' # For MailHog → both are False.
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@vehicleapp.com') # Sender email address


# OTP Configuration
OTP_EXPIRY_SECONDS = 300  # 5 minutes for registration OTP
PASSWORD_RESET_OTP_EXPIRY_SECONDS = 600  # 10 minutes for password reset OTP
PASSWORD_RESET_TOKEN_EXPIRY_SECONDS = 900  # 15 minutes for reset token



# CKEditor 5 Configuration
CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': [
            'heading', '|',
            'bold', 'italic', 'link', 'bulletedList', 'numberedList', '|',
            'blockQuote', 'insertTable', '|',
            'undo', 'redo'
        ],
        'height': 300,
        'width': '100%',
    },
    'extends': {
        'blockToolbar': [
            'paragraph', 'heading1', 'heading2', 'heading3', '|',
            'bulletedList', 'numberedList', '|',
            'blockQuote',
        ],
        'toolbar': [
            'heading', '|',
            'outdent', 'indent', '|',
            'bold', 'italic', 'link', 'underline', 'strikethrough',
            'code', 'subscript', 'superscript', 'highlight', '|',
            'codeBlock', 'sourceEditing', 'insertImage',
            'bulletedList', 'numberedList', 'todoList', '|',
            'blockQuote', 'imageUpload', '|',
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor',
            'mediaEmbed', 'removeFormat', 'insertTable',
        ],
        'image': {
            'toolbar': [
                'imageTextAlternative', '|',
                'imageStyle:alignLeft',
                'imageStyle:alignRight',
                'imageStyle:alignCenter',
                'imageStyle:side', '|'
            ],
            'styles': [
                'full',
                'side',
                'alignLeft',
                'alignRight',
                'alignCenter',
            ]
        },
        'table': {
            'contentToolbar': [
                'tableColumn', 'tableRow', 'mergeTableCells',
                'tableProperties', 'tableCellProperties'
            ],
            'tableProperties': {
                'borderColors': [],
                'backgroundColors': []
            },
            'tableCellProperties': {
                'borderColors': [],
                'backgroundColors': []
            }
        },
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'},
                {'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'},
                {'model': 'heading3', 'view': 'h3', 'title': 'Heading 3', 'class': 'ck-heading_heading3'}
            ]
        }
    },
    'list': {
        'properties': {
            'styles': 'true',
            'startIndex': 'true',
            'reversed': 'true',
        }
    }
}

# CKEditor 5 file upload settings
CKEDITOR_5_UPLOAD_PATH = "uploads/"
CKEDITOR_5_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"


# Rate Limiting Configuration
RATELIMIT_ENABLE = False  # False: Disable rate limiting for development
RATELIMIT_USE_CACHE = 'default'  # Use Redis cache
RATELIMIT_VIEW_403 = True  # Return 403 instead of default behavior

# Optional: Custom rate limit failure response
RATELIMIT_FAIL_OPEN = False  # If True, allows requests when rate limit backend fails

# Logging for rate limits (optional)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'ratelimit.log',
        },
    },
    'loggers': {
        'django.ratelimit': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
        },
    },
}



# Firebase Configuration
# FIREBASE_CREDENTIALS_PATH = os.path.join(BASE_DIR, 'firebase-credentials.json')

# # Initialize Firebase Admin SDK
# if os.path.exists(FIREBASE_CREDENTIALS_PATH):
#     cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
#     firebase_admin.initialize_app(cred)
# else:
#     print("WARNING: Firebase credentials not found. Push notifications disabled.")

# Channels Configuration (for WebSocket)
ASGI_APPLICATION = 'core.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(os.getenv('REDIS_HOST', 'localhost'), int(os.getenv('REDIS_PORT', '6379')))],
        },
    },
}


# AI Service Configuration
# AI_DIAGNOSTIC_BASE_URL = os.getenv('AI_DIAGNOSTIC_BASE_URL', 'http://165.101.214.252:8000/')
# AI_DIAGNOSTIC_ENDPOINT = f'{AI_DIAGNOSTIC_BASE_URL}/api/diagnose/'
# AI_REQUEST_TIMEOUT = 30  # seconds


# iOS In-App Purchase Configuration
# IOS_SHARED_SECRET = os.getenv('IOS_SHARED_SECRET', '')
# IOS_SANDBOX_MODE = os.getenv('IOS_SANDBOX_MODE', 'True') == 'True'

# # Android In-App Purchase Configuration
# ANDROID_PACKAGE_NAME = os.getenv('ANDROID_PACKAGE_NAME', 'com.autointel.vehicle')
# GOOGLE_PLAY_SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, 'google-play-service-account.json')


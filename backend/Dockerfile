FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN useradd --create-home --uid 1000 app

COPY requirements/base.txt requirements/base.txt
RUN pip install -r requirements/base.txt

COPY --chown=app:app . .
RUN mkdir -p /app/staticfiles /app/media && chown app:app /app/staticfiles /app/media
USER app

# Collect Django Admin static files at build time (served by WhiteNoise under config.settings.prod).
# The values below exist only for this RUN step (they are not stored in the image environment) and satisfy
# prod.py's fail-fast checks; collectstatic opens no database or Redis connection.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_SECRET_KEY=build-time-only-not-a-real-secret-key-0000000000 \
    DJANGO_ALLOWED_HOSTS=build.invalid \
    DATABASE_URL=postgres://build:build@build.invalid:5432/build \
    REDIS_URL=redis://build.invalid:6379/0 \
    python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
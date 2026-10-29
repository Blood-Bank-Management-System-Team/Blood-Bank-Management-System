FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GUNICORN_CMD_ARGS="--workers 3 --access-logfile -"

WORKDIR /app

# Run as an unprivileged user
RUN addgroup --system app && adduser --system --ingroup app --no-create-home app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .
RUN chmod +x /app/docker-entrypoint.sh \
    && DJANGO_DEBUG=True python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles

USER app

EXPOSE 8000
# Migrations run at container start (see docker-entrypoint.sh), not at build time.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]

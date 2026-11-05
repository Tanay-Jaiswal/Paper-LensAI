# PaperLens AI web app as a container (docs/DEPLOY.md). Build: docker build -t paperlens .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PAPERLENS_DATA=/data PAPERLENS_HOSTED=1 PORT=8000
WORKDIR /app

ARG INSTALL_AI=0
COPY requirements.txt requirements-ai.txt ./
# pytest and httpx in requirements.txt are only for the tests; they are small and keep one requirements file
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$INSTALL_AI" = "1" ]; then pip install --no-cache-dir -r requirements-ai.txt; fi

COPY paperlens ./paperlens
COPY web ./web
# the "Load synthetic demo papers" button generates its papers with eval/synth.py
COPY eval/__init__.py eval/synth.py ./eval/

RUN useradd --create-home paperlens && mkdir -p /data && chown paperlens /data
USER paperlens
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8000'))"
# hosts such as Render and Railway tell the app which port to use through $PORT
CMD ["sh", "-c", "python -m paperlens serve --host 0.0.0.0 --port ${PORT}"]

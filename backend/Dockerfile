# Python 3.12, not 3.13 -- this app has never actually been tested
# against 3.13 anywhere in this build (CI pins 3.12, every local test
# run throughout development used 3.12.3). The mismatch was invisible
# until a real deploy actually tried to build the image: 3.13 broke
# because psycopg2-binary==2.9.9 has no precompiled wheel for it and
# fails compiling from source (a real C-API incompatibility, not a
# transient issue -- _PyInterpreterState_Get's signature changed).
# Matching the version everything else in this repo already runs on
# is the fix, not chasing a newer psycopg2-binary pin that's untested
# here.
FROM python:3.12-slim

WORKDIR /srv/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

CMD ["./docker-entrypoint.sh"]

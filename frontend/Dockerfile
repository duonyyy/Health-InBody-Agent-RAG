FROM python:3.10.12-slim-bullseye

WORKDIR /usr/src/app/

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY requirements.txt /usr/src/app/

# Keep dependencies in a cacheable layer so source-only changes rebuild fast.
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app/
RUN chmod +x /usr/src/app/entrypoint.sh

# run entrypoint.sh
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]

FROM python:3.10-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends \
        python3-dev \
        default-libmysqlclient-dev \
        build-essential \
        pkg-config -y \
    && rm -rf /var/lib/apt/lists/*

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH "${PYTHONPATH}:/usr/src/app/src"

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/app/requirements.txt
RUN pip install -r requirements.txt
# --use-deprecated=legacy-resolver

# copy entrypoint.sh
COPY ./entrypoint.sh /usr/src/app/entrypoint.sh

# set execute permission for entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

# copy project
COPY . /usr/src/app/

# run entrypoint.sh
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]

# default command to run the app
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]

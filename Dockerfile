# A dockerfile must always start by importing the base image.
# We use the keyword 'FROM' to do that.
# In our example, we want import the python image.
# So we write 'python' for the image name and 'latest' for the version.
FROM python:3.6

RUN apt-get -y update && apt-get -y upgrade
RUN apt-get install -y apt-utils
RUN apt-get install -y cron

RUN python3.6 -m pip install --upgrade pip
RUN apt-get install -y python3-numpy python-matplotlib python3-matplotlib python3-pandas


# In order to launch our python code, we must import it into our image.
# We use the keyword 'COPY' to do that.
# The first parameter 'main.py' is the name of the file on the host.
# The second parameter '/' is the path where to put the file on the image.
# Here we put the file at the image root folder.

COPY requirements/requirements.txt /
RUN pip install --no-cache-dir matplotlib
RUN pip install --no-cache-dir mplfinance
RUN pip install -r requirements.txt

RUN touch /var/log/last_run_btc.out
RUN touch /var/log/last_run_eth.out
RUN mkdir /code
WORKDIR /code
ADD ./gemini_dca/ /code/
COPY ./cron/crontab /etc/cron.d/cjob
RUN chmod 0644 /etc/cron.d/cjob
ENV PYTHONUNBUFFERED 1
CMD cron -f
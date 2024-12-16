FROM python:bookworm

RUN mkdir /chrome
WORKDIR /chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt update
RUN apt install -y ./google-chrome-stable_current_amd64.deb

RUN mkdir /app
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY main.py main.py

ENTRYPOINT python main.py --output /out --userjson /json --cookies /cookies --logs /logs

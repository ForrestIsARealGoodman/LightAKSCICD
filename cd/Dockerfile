FROM python:3

WORKDIR /usr/src/app

#Install lib
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

#Install vim
RUN  apt-get update && apt-get install -y vim

#Install terraform
RUN curl -fsSL https://apt.releases.hashicorp.com/gpg | apt-key add -
RUN apt-get install -y lsb-release
RUN apt-get install -y software-properties-common
RUN apt-get update
RUN apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"

COPY . .

FROM centos
Maintainer QA-APRICO
ENV container docker

RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == \
systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;

# Install anything. The service you want to start must be a SystemD service.

RUN yum -y update
RUN yum install -y maven
RUN yum install -y unzip
RUN yum install -y sudo
RUN yum install -y nano
RUN yum install -y bsdtar

# download the  Java jdk11
RUN yum -y remove java
RUN yum -y install java-11-openjdk

#Configure python
#RUN dnf install -y python3
RUN yum -y install python3-pip
RUN alternatives --set python /usr/bin/python3
RUN ln -s /usr/bin/pip3 /usr/bin/pip
RUN python3 -m pip install pandas
RUN python3 -m pip install aniso8601
RUN python3 -m pip install lxml
RUN python3 -m pip install dirtyjson
RUN python3 -m pip install openpyxl

#Copy validation engine, ruleset library and python scripts
COPY remote/* /home/tmp/

#Project ENV
ARG StandaloneValidationTool

#Project deployment
#RUN tar xvzf /home/tmp/${StandaloneValidationTool}.tar.gz  -C /home/
WORKDIR '/home/tmp'
RUN tar xvzf "$(find standalone-validation-tool*.tar.gz)"
RUN mv "$(find -type d -name 'standalone-validation-tool*')" /home/standalone-validation-tool

WORKDIR '/home/tmp'
RUN unzip "$(find configured-rule-set-lib*.zip)"
RUN rm -rf /home/standalone-validation-tool/workspace/rule-set-library/*
RUN mv "$(find -maxdepth 1 -type d -name 'RSL*')"/* /home/standalone-validation-tool/workspace/rule-set-library

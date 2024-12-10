FROM ubuntu:24.04 AS spython-base
RUN export DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get install -y --no-install-recommends git gh
RUN apt-get install -y --no-install-recommends less
RUN apt-get install -y --no-install-recommends python3
RUN apt-get install -y --no-install-recommends python3.12-venv python3-pip
RUN apt-get install -y --no-install-recommends build-essential
RUN apt-get install -y --no-install-recommends ruby ruby-dev
RUN apt-get install -y --no-install-recommends bundler
RUN apt-get install -y --no-install-recommends nodejs
RUN apt-get install -y --no-install-recommends npm
RUN apt-get install -y --no-install-recommends ditaa
RUN apt-get install -y --no-install-recommends libyaml-dev
RUN apt-get clean autoclean
RUN apt-get autoremove -y
RUN rm -rf /var/lib/{apt, dpkg, cache, log}

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace

RUN export DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get install -y --no-install-recommends git gh
RUN apt-get install -y --no-install-recommends less
RUN apt-get install -y --no-install-recommends python3
RUN apt-get install -y --no-install-recommends python3.12-venv
RUN apt-get install -y --no-install-recommends python3-pip
RUN apt-get install -y --no-install-recommends build-essential
RUN apt-get install -y --no-install-recommends ruby
RUN apt-get install -y --no-install-recommends ruby-dev
RUN apt-get install -y --no-install-recommends bundler
RUN apt-get install -y --no-install-recommends nodejs
RUN apt-get install -y --no-install-recommends npm
RUN apt-get install -y --no-install-recommends ditaa
RUN apt-get install -y --no-install-recommends libyaml-dev
RUN apt-get install -y --no-install-recommends cmake
RUN apt-get install -y --no-install-recommends g++
RUN apt-get install -y --no-install-recommends clang-format
RUN apt-get install -y --no-install-recommends clang-tidy
RUN apt-get install -y --no-install-recommends libelf-dev
RUN apt-get clean autoclean
RUN apt-get autoremove -y
RUN rm -rf /var/lib/{apt,dpkg,cache,log}/*

WORKDIR /workspace

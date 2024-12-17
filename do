#!/bin/bash

ROOT=$(dirname $(realpath $BASH_SOURCE[0]))
if [ -v DEVCONTAINER_ENV ]; then
  BUNDLE=bundle
else
  source $ROOT/bin/setup
fi

if [ "$1" == "clean" ]; then
  ${ROOT}/bin/clean
else
  # really long way of invoking rake, but renamed to 'do'
  $BUNDLE exec --gemfile $ROOT/Gemfile ruby -r rake -e "Rake.application.init('do');Rake.application.load_rakefile;Rake.application.top_level" -- $@
fi

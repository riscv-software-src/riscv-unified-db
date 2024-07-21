#!/bin/bash

ROOT=$(dirname $(realpath $BASH_SOURCE[0]))
source $ROOT/bin/setup

# really long way of invoking rake, but renamed to 'do'
$BUNDLE exec --gemfile $ROOT/Gemfile ruby -r rake -e "Rake.application.init('do');Rake.application.load_rakefile;Rake.application.top_level" -- $@

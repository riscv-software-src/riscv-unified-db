#!/bin/bash

ROOT=$(dirname $(realpath $BASH_SOURCE[0]))
source $ROOT/bin/setup

# ROOT=$(dirname $(realpath $BASH_SOURCE[0]))
# export PATH=/pkg/qct/software/ruby/2.7.2/bin:/pkg/qct/software/llvm/15.0.5/bin:${PATH}
# if [ ! -d "${ROOT}/.gems" ]; then
#   bundle install
# fi

$BUNDLE exec --gemfile $ROOT/Gemfile rake -f $ROOT/tasks/top.rake $@

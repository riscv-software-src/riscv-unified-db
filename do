#!/usr/bin/env bash

ROOT=$(dirname $(realpath ${BASH_SOURCE[0]}))

[ $# -eq 0 ] && {
  ./do --tasks
  exit 0
}

if [ "$1" == "clobber" ]; then
  ${ROOT}/bin/clobber
  exit $?
elif [ "$1" == "clean" ]; then
  ${ROOT}/bin/clean
  exit $?
fi

source $ROOT/bin/setup

# Check if setup was successful
if [ $? -ne 0 ]; then
  echo "Setup failed, attempting to continue anyway..." >&2
fi

# Ensure BUNDLE is set
if [ -z "$BUNDLE" ]; then
  echo "BUNDLE not set, using default bundle command" >&2
  BUNDLE="bundle"
fi

# really long way of invoking rake, but renamed to 'do'
$BUNDLE exec --gemfile $ROOT/Gemfile ruby -r rake -e "Rake.application.init('do');Rake.application.load_rakefile;Rake.application.top_level" -- "$@"

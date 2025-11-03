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

# really long way of invoking rake, but renamed to 'do'
EXEC=( exec --gemfile "$ROOT/Gemfile" ruby -r rake -e '"Rake.application.init('"'do'"');Rake.application.load_rakefile;Rake.application.top_level"' -- "$@" )
if [ "${CONTAINER_TYPE}" == "docker" -o "${CONTAINER_TYPE}" == "podman" ]; then
  ${BASH} -c "$(printf "%s && " "${CONTAINER_SETUP_CMD[@]:-true}") bundle ${EXEC[*]}"
else
  $BUNDLE "${EXEC[@]}"
fi

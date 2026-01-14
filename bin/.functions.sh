#!/bin/bash

get_container_type() {
  # get the container type
  #
  # use, in priority order:
  #  1. devcontainer, if DEVCONTAINER_ENV is set in the environment
  #  2. the type stored in .container-type
  #  3. Docker, if DOCKER is set in the environment
  #  4. Podman, if PODMAN is set in the environment
  #  5. Singularity, if SINGULARITY is set in the environment
  #  6. The choice made by the user, which will be cached in .container-type
  local container_type=
  if [ -v DEVCONTAINER_ENV ]; then
  container_type=devcontainer
  elif [ -v SINGULARITY_NAME ]; then
  # already in a container
  container_type=devcontainer
  elif [ -f "${ROOT}/.container-type" ]; then
  container_type=$(cat ${ROOT}/.container-type)
  elif [ -v DOCKER ]; then
  container_type=docker
  elif [ -v PODMAN ]; then
  container_type=podman
  elif [ -v SINGULARITY ]; then
  container_type=singularity
  else
    echo -e "UDB tools run in a container. Docker, Podman, and Singularity/Apptainer are supported.\\n\\n1. Docker\\n2. Podman\\n3. Singularity\\n"
    while true; do
      echo "Which would you like to use? (1/2/3) "
      read -r ans
      case $ans in
          [1]* ) container_type=docker; break;;
          [2]* ) container_type=podman; break;;
          [3]* ) container_type=singularity; break;;
          * ) echo -e "\\nPlease answer 1, 2, or 3.";;
      esac
    done
  fi

  echo "$container_type"
}

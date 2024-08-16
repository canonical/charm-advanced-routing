PYTHON := /usr/bin/python3

PROJECTPATH=$(dir $(realpath $(MAKEFILE_LIST)))
ifndef CHARM_LAYERS_DIR
	CHARM_LAYERS_DIR=${PROJECTPATH}/layers
endif
ifndef CHARM_INTERFACES_DIR
	CHARM_INTERFACES_DIR=${PROJECTPATH}/interfaces
endif
ifdef CONTAINER
	BUILD_ARGS="--destructive-mode"
endif
METADATA_FILE="src/metadata.yaml"
CHARM_NAME=$(shell cat ${PROJECTPATH}/${METADATA_FILE} | grep -E "^name:" | awk '{print $$2}')

help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make help - show this text"
	@echo " make clean - remove unneeded files"
	@echo " make submodules - make sure that the submodules are up-to-date"
	@echo " make submodules-update - update submodules to latest changes on remote branch"
	@echo " make build - build the charm"
	@echo " make lint - run flake8 and black --check"
	@echo " make black - run black and reformat files"
	@echo " make unittests - run the tests defined in the unittest subdirectory"
	@echo " make functional - run the tests defined in the functional subdirectory"
	@echo " make test - run lint, unittests and functional targets"
	@echo ""

clean:
	@echo "Cleaning charmcraft"
	@charmcraft clean
	@echo "Cleaning existing chamr files"
	@rm -rf ${PROJECTPATH}/${CHARM_NAME}*.charm

submodules:
	@echo "Cloning submodules"
	@git submodule update --init --recursive

submodules-update:
	@echo "Pulling latest updates for submodules"
	@git submodule update --init --recursive --remote --merge

build: clean
	@echo "Building charm to base directory ${PROJECTPATH}/${CHARM_NAME}.charm"
	@-git rev-parse --abbrev-ref HEAD > ./src/repo-info
	@charmcraft -v pack ${BUILD_ARGS}
	@bash -c ./rename.sh

lint:
	@echo "Running lint checks"
	@tox -e lint

black:
	@echo "Reformat files with black"
	@tox -e black

unittests:
	@echo "Running unit tests"
	@tox -e unit

functional: build
	@echo "Executing functional tests with ${PROJECTPATH}/${CHARM_NAME}.charm"
	@CHARM_LOCATION=${PROJECTPATH} tox -e func

test: lint unittests functional
	@echo "Tests completed for charm ${CHARM_NAME}."

# The targets below don't depend on a file
.PHONY: help submodules submodules-update clean build lint black unittests functional test

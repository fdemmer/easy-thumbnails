[private]
default:
    @just --list --unsorted

gha-update:
    uvx gha-update

clean:
    rm -rf build dist htmlcov
    rm -rf *.egg-info
    rm -f .coverage

test env="":
    uvx --with tox-uv tox {{ if env == "" { "--parallel auto" } else { "-e " + env } }}

coverage env="py314-dj52-svg":
    #!/usr/bin/env bash
    if [ ! -f .coverage ]; then
        uvx --with tox-uv tox -e {{env}}
    fi
    uvx --with tox-uv tox exec -e {{env}} -- coverage html

docs:
    rm -rf docs/_build
    uv run --with sphinx --with-requirements docs/requirements.txt \
        sphinx-build -b html docs docs/_build/html

build:
    uvx --from build pyproject-build

publish-test: clean build
    uvx twine upload -r testpypi dist/*

publish: clean build
    #!/usr/bin/env bash
    status=$(git status --porcelain)
    if [ -z "$status" ]; then
        uvx twine upload -r fdemmer-easy-thumbnails dist/*
    else
        echo "Aborting upload: working directory is dirty" >&2
        exit 1
    fi

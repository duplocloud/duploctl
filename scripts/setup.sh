#!/usr/bin/env bash

mkdir -p config dist dist/docs

pip install --editable .[build,test,aws,docs]

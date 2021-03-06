#!/bin/bash

# This file is part of scarlett.
# Copyright 2014, Malcolm Jones.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# Note: Plugins do not support versions with words in them. The supported
#       format is numbers with decimals for example 3.0.0

version=$1

# bump the version of scarlett
sed -i "s/^__version__ = .*/__version__ = '$version'/" scarlett/__init__.py

# search for plugins and bump version
#echo "Bumping plugin versions to $version"
#find src/scarlett/plugins -name "*.scarlett-plugin" -print | xargs sed -i "s/^Version = .*/Version = $version/"

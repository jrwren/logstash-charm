# This file is part of the logstash charm.
# Copyright (C) 2013-2015 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License version 3, as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

PYTHON := /usr/bin/env python
TESTS = $(shell find -L tests -type f -executable | sort)

.PHONY: $(TESTS) clean check deploytest sync test unittest

unittest:
	nosetests -v --with-coverage --cover-package hooks hooks

check:
	flake8 --exclude hooks/charmhelpers hooks
	charm proof

test: check unittest

sync:
	mkdir -p bin
	bzr cat lp:charm-helpers/tools/charm_helpers_sync/charm_helpers_sync.py > bin/charm_helpers_sync.py
	$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers-sync.yaml

clean:
	find . -name \*.pyc -delete
	find . -name '*.bak' -delete

$(TESTS):
	$@

deploytest: $(TESTS)

fat:
	mkdir -p files/debian/dists/stable/main/binary-amd64
	mkdir -p files/debian/pool/main/l/logstash
	curl -q -s -o files/GPG-KEY-elasticsearch http://packages.elasticsearch.org/GPG-KEY-elasticsearch
	curl -q -s -o files/debian/dists/stable/main/binary-amd64/Packages http://packages.elasticsearch.org/logstash/1.4/debian/dists/stable/main/binary-amd64/Packages
	curl -q -s -o files/debian/pool/main/l/logstash/logstash_1.4.5-1-a2bacae_all.deb http://packages.elasticsearch.org/logstash/1.4/debian/pool/main/l/logstash/logstash_1.4.5-1-a2bacae_all.deb
	curl -q -s -o files/debian/dists/stable/Release.gpg http://packages.elasticsearch.org/logstash/1.4/debian/dists/stable/Release.gpg
	curl -q -s -o files/debian/dists/stable/Release http://packages.elasticsearch.org/logstash/1.4/debian/dists/stable/Release
	./fatifyconfig.py

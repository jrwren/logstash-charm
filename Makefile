# This file is part of the mongodb charm.
# Copyright (C) 2013 Canonical Ltd.
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

unittest:
	@echo Starting Tests	
	.venv/bin/nosetests --nologcapture unit_tests	

lint:
	@flake8 --exclude hooks/charmhelpers hooks
	@flake8 --exclude hooks/charmhelpers unit_tests
	@charm proof
sync:
	@mkdir -p bin
	@bzr cat lp:charm-helpers/tools/charm_helpers_sync/charm_helpers_sync.py > bin/charm_helpers_sync.py	
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers-sync.yaml

clean:
	@find . -name \*.pyc -delete
	@find . -name '*.bak' -delete
	@rm -rf .venv

.venv:
	sudo apt-get install python-virtualenv python-apt
	virtualenv .venv --system-site-packages
	.venv/bin/pip install nose pyyaml mock -I

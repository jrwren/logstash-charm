#!/usr/bin/python
import json
import os
import socket
import subprocess
import sys
import pdb

from charmhelpers.core.hookenv import (
    Hooks,
    relation_get,
    relation_ids,
)

from charmhelpers.core.host import (
    service
)

from charmhelpers.core.fetch import (
    apt_update,
    apt_install
)

LS_URL = ("https://download.elasticsearch.org/"
          "logstash/logstash/logstash-1.4.1.tar.gz")
LS_FNAME = os.path.basename(LS_URL)
LS_DIR = "/opt/logstash"
LS_CONF_DIR = "/etc/logstash.d"

hooks = Hooks()

@hooks.hook('install')
def install():
    packages = ['openjdk-7-jre-headless', 'python-jinja2']    


    if not os.path.exists(LS_DIR):
        os.mkdir(LS_DIR)

    ls_tgz = os.path.join(
        os.environ['CHARM_DIR'], 'files', LS_FNAME)

    if not os.path.exists(ls_tgz):
        ls_tgz = os.path.join('/tmp', LS_FNAME)
        subprocess.check_call(['curl', '-o', ls_tgz, LS_URL])
        subprocess.check_call(
            ['md5sum', '-c', os.path.join(
                os.environ['CHARM_DIR'], 'files', 'checksums')])

    subprocess.check_call([
        'tar', '-xzv', '--strip-components=1',
        '-C', "/opt/logstash", '-f', ls_tgz])


@hooks.hook('config-changed')
def config_changed():
    service('restart', 'logstash-indexer')

@hooks.hook('client-relation-joined')
def get_elasticsearch():
    # Only supports a single scale unit (no scale-out of logstash-indexer)
    rid = relation_ids('client')[0]
    unit = relation_list(rid)[0]
    
    hookenv.relation_get('host', rid, unit)
    
    write_file(
        '/etc/logstash.d/70-juju-outputs.conf',
        'outputs.conf.template',
        dict(elasticsearch=outputs_es))
    


##########
## generic helpers

class AttrDict(dict):

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


def write_file(path, template, data):
    """Render the named jinja 'template' with the given template 'data' to
    'path'. Return true if the contents of the path changed.
    """
    template = get_template(template)
    content = template.render(**data)
    if os.path.exists(path):
        with open(path) as fh:
            config = fh.read()
            if config == content:
                return False
    with open(path, 'w') as fh:
        fh.write(content)
    return True


def get_template(name):
    template_path = os.path.join(os.environ['CHARM_DIR'], 'files', name)
    with open(template_path) as fh:
        content = fh.read()
    return Template(content)


def get_open_port(host=""):
    """Get an open port on the machine.
    """
    temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    temp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    temp_sock.bind((host, 0))
    port = temp_sock.getsockname()[1]
    temp_sock.close()
    del temp_sock
    return port


if __name__ == "__main__":
    # execute a hook based on the name the program is called by
    hooks.execute(sys.argv)


#!/usr/bin/python
import os
import subprocess
import sys
import shlex
import shutil

from charmhelpers.core.host import service, adduser, mkdir, chownr
from charmhelpers.core.fetch import apt_update, apt_install
from charmhelpers.core.fetch.archiveurl import download_and_validate
from charmhelpers.core.hookenv import (
    Hooks,
    relation_get,
    relation_ids,
    relation_list,
    open_port,
    close_port,
    config,
)

# Constants

LS_USER = 'logstash'
LS_URL = config()['logstash_url']
LS_FNAME = os.path.basename(LS_URL)
LS_DIR = os.path.join(os.path.sep, "opt", "logstash")
LS_CONF_DIR = os.path.join(os.path.sep, "etc", "logstash.d")
LS_LOG = os.path.join(os.path.sep, "var", "log", "logstash.log")

hooks = Hooks()
cfg = config()

@hooks.hook('install')
def install():
    packages = ['openjdk-7-jre-headless', 'python-jinja2']
    apt_update()
    apt_install(packages, FATAL=True)

    uid = adduser(LS_USER).pw_uid

    mkdir(LS_DIR, LS_USER)
    mkdir(LS_CONF_DIR, LS_USER)

    # touch the log
    with open(LS_LOG, 'a'):
        os.utime(LS_LOG, None)
    os.chown(LS_LOG, uid)

    conf_src = os.path.join(os.environ['CHARM_DIR'], 'files', 'logstash.conf')
    conf_dest = os.path.join(os.path.sep, 'etc', 'init', 'logstash.conf')
    shutil.copyfile(conf_src, conf_dest)

@hooks.hook('config-changed')
def config_changed():

    ls_tgz = os.path.join(os.environ['CHARM_DIR'], 'files', LS_FNAME)

    # sorry if you reboot the server, we're fetching it again unless
    # you fatpacked the charm. YOLO DORITOS
    if not os.path.exists(ls_tgz):
        link = cfg['logstash_url']
        sum = cfg['logstash_sum']
        tpath = download_and_validate(link, sum)

        cmd = 'tar -xvz --strip-components=1 -C /opt/logstash -f {}'
        subprocess.check_call(shlex.split(cmd.format(tpath)))

    service('restart', 'logstash-indexer')



@hooks.hook('start')
def start():
  open_port(9300)

@hooks.hook('stop')
def stop():
  close_port(9300)

@hooks.hook('client-relation-joined')
def client_joined():
    # Only supports a single scale unit (no scale-out of logstash-indexer)
    rid = relation_ids('client')[0]
    unit = relation_list(rid)[0]

    relation_get('host', rid, unit)

    # write_file(
    #     '/etc/logstash.d/70-juju-outputs.conf',
    #     'outputs.conf.template',
    #     dict(elasticsearch=outputs_es))

if __name__ == "__main__":
    # execute a hook based on the name the program is called by
    hooks.execute(sys.argv)

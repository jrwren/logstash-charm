logstash-juju-charm
==============================

Juju Charm for logstash

This charm uses deb packages from http://logstash.net/docs/1.4.2/repositories
or whatever is configured by the apt-repository setting.

Inputs :
  TCP - relate a charm which supports writing log to TCP port
Outputs :
  elasticsearch - create relationship with elasticsearch charm

*disabled the web service ...   use kibana! (also joinable charm)*

example 1 - NOOP ELK
=====================================

    juju deploy local:trusty/logstash
    juju deploy local:trusty/elasticsearch
    juju deploy local:trusty/kibana
    juju add-relation kibana elasticsearch:rest
    juju add-relation logstash elasticsearch
    juju expose kibana

http://ip-of-kibana

example 2 - something logging
=====================================

    juju deploy local:trusty/logstash
    juju deploy local:trusty/elasticsearch
    juju deploy local:trusty/kibana
    juju add-relation kibana elasticsearch:rest
    juju add-relation logstash elasticsearch
    juju deploy local:trusty/somecharmwhichlogs
    juju add-relation logstash somecharmwhichlogs
    juju expose kibana

http://ip-of-kibana


Using the charm in fat mode
=====================================

In the course of operations, it may come to pass, the need to deploy a
charm which does not use an external repository.
Rather than maintain a different charm, this charm has the ability to
convert itself to a fat charm. Run the `make fat` command to fetch
the logstash package from the internet and insert it into this tree.

When the charm is in fat mode, the apt-repository and apt-key-url are
immutable settings. You can change them, but that will remove the
charm from fat mode and trigger remote access for apt-repository
and apt-key-url.

#!/usr/bin/env python

import os
import yaml

def main():
    if os.environ.get('NOCONF'):
        return

    with open('config.yaml') as configfile:
        config = yaml.load(configfile)
    config['options']['apt-key-url'] = ''
    config['options']['apt-repository'] = ''

    with open('config.yaml', 'w') as configfile:
        yaml.dump(config, configfile)

if __name__ == '__main__':
    main()

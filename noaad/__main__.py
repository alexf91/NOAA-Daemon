#
# Copyright 2017 Alexander Fasching OE5TKM
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import print_function

import sys
import os
import argparse
import setproctitle
import trollius as asyncio
import configparser
import logging

from .configuration import default
from .noaad import NOAADaemon


def main():
    setproctitle.setproctitle('noaad')
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)

    # Some users might use XDG_CONFIG_HOME, so we check for it.
    xdgdir = os.getenv('XDG_CONFIG_HOME')
    if xdgdir:
        cfgdir = os.path.join(xdgdir, 'noaa-daemon')
    else:
        cfgdir = os.path.expanduser('~/.config/noaa-daemon')

    # The default settings are not really usable, so we need an option to exit
    # immediately and edit the configuration file.
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action='store_true',
            help='initialize configuration and exit')
    parser.add_argument('--conf', '-c', default='default.conf',
            help='use a specific configuration file')
    parser.add_argument('--list', '-l', action='store_true',
            help='list available configuration files')

    args = parser.parse_args()
    cfgfile = os.path.join(cfgdir, args.conf)

    if not os.path.exists(cfgdir):
        try:
            os.makedirs(cfgdir)
        except os.error as e:
            print(e, file=sys.stderr)
            return 1

    if args.list:
        print('Existing configuration files:')
        for p in os.listdir(cfgdir):
            if p.endswith('.conf'):
                print(p)
        return 0

    if not os.path.exists(cfgfile):
        with open(cfgfile, 'w') as fp:
            default.write(fp)

    # Terminate if we only initialize
    if args.init:
        return 0

    # Read the configuration the user requested
    config = configparser.ConfigParser()
    if not config.read(cfgfile):
        print('Could not read configuration file', file=sys.stderr)
        return 1

    config.cfgdir = cfgdir
    noaad = NOAADaemon(config)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(noaad())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == '__main__':
    sys.exit(main() or 0)

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

import os
import logging
import trollius as asyncio
from trollius import From
import urllib2
import ephem
import datetime as dt


class NOAADaemon(object):
    """
    The main control services used by the NOAA-Daemon:

    * Initialize and update NORAD data: on startup and every 24 hours at midnight (UTC)

    * Plan recording sessions: we abort running recording in favor of
        passes with high maximum elevation. This will occasionally lead to
        incomplete images, but should maximize the overall quality, as
        concurrent high elevation passes are relatively unlikely.
        New schedules are planned every time the NORAD data is updated.

    * Control the GNU Radio receiver

    All services are executed using asyncio (trollius).
    This class implements __call__, so it's sufficient to call
    the object in an event loop.
    """
    def __init__(self, config):
        self.config = config
        self.log = logging.getLogger('NOAADaemon')
        self.tledata = dict()

        self.updateTask = None


    @asyncio.coroutine
    def __call__(self):
        """ Main initializer """
        # Download the TLE data
        rc = yield From(self.updateTLE())
        if not rc:
            self.log.error('Downloading TLE data failed')

        rc = yield From(self.readTLE())
        if not rc:
            self.log.error('Reading TLE data failed')

        self.updateTask = asyncio.async(self.dailyUpdate())


    @asyncio.coroutine
    def dailyUpdate(self):
        """ Update TLE data every day at 0:00 UTC """
        now = dt.datetime.utcnow()
        tmrw = dt.datetime.combine(dt.date.today() + dt.timedelta(days=1), dt.time())

        delta = (tmrw - now).total_seconds()
        yield From(asyncio.sleep(delta))

        while True:
            rc = yield From(self.updateTLE())
            if not rc:
                self.log.error('Downloading TLE data failed')

            rc = yield From(self.readTLE())
            if not rc:
                self.log.error('Reading TLE data failed')

            yield From(asyncio.sleep(24 * 3600))


    @asyncio.coroutine
    def updateTLE(self):
        """ Download new TLE data and write it to the configuration directory. """
        try:
            r = urllib2.urlopen('https://celestrak.com/NORAD/elements/weather.txt', timeout=30)
            tledata = r.read()
            with open(os.path.join(self.config.cfgdir, 'satellites.tle'), 'w') as fp:
                fp.write(tledata)

            return True

        except Exception as e:
            self.log.error(e)
            return False


    @asyncio.coroutine
    def readTLE(self):
        """
        Read TLE data from disk and populate the tledata dictionary.
        This also checks if the file really contains TLE data.
        Returns True on success and False on error.
        """
        tlepath = os.path.join(self.config.cfgdir, 'satellites.tle')
        if os.path.exists(tlepath):
            with open(os.path.join(self.config.cfgdir, 'satellites.tle')) as fp:
                lines = [line.strip() for line in fp.readlines()]

            for i in range(0, len(lines), 3):
                name = lines[i]
                line1 = lines[i+1]
                line2 = lines[i+2]

                try:
                    sat = ephem.readtle(name, line1, line2)
                except ValueError:
                    return False

                if name in self.config.sections():
                    self.tledata[name] = sat

            return True

        else:
            return False

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

from __future__ import print_function, division

import os
import logging
import trollius as asyncio
from trollius import From
import urllib2
import ephem
import datetime as dt
import math

from .receiver import Receiver


class NOAADaemon(object):
    """
    The main control services used by the NOAA-Daemon:

    * Initialize and update NORAD data: on startup and every 24 hours at midnight (UTC)

    * Plan recording sessions: passes are recorded on a first-come first-serve basis.
        This might produce incomplete images, since only one pass can be recorded
        at the same time.

    * Control the GNU Radio receiver

    All services are executed using asyncio (trollius).
    This class implements __call__, so it's sufficient to call
    the object in an event loop.
    """
    def __init__(self, config):
        self.config = config
        self.log = logging.getLogger('NOAADaemon')
        self.tledata = dict()

        self.observer = ephem.Observer()
        self.observer.lat = config['Location']['latitude']
        self.observer.lon = config['Location']['longitude']
        self.observer.elevation = float(self.config['Location']['altitude'])
        self.observer.pressure = 0

        self.tleFuture = None
        self.testFuture = None

        self.receiverLock = asyncio.Lock()
        self.receiver = Receiver(self.config)


    @asyncio.coroutine
    def __call__(self):
        """ Main initializer """
        # Download the TLE data
        yield From(self.updateTLE())
        yield From(self.test())

        for name in self.tledata:
            asyncio.ensure_future(self.recordPass(name))


    @asyncio.coroutine
    def test(self):
        tasks = asyncio.Task.all_tasks()
        print('Number of tasks:', len(tasks))

        #self.receiver.startRecording('NOAA 19')
        #yield From(asyncio.sleep(10))
        #self.receiver.stopRecording()

        ts = dt.datetime.utcnow() + dt.timedelta(seconds=30)
        self.testFuture = asyncio.ensure_future(self.scheduleAt(self.test(), ts))


    @asyncio.coroutine
    def waitUntil(self, target):
        """
        Wait at least until 'target', where 'target' is a
        datetime.datetime object. All times are in UTC.
        """
        while dt.datetime.utcnow() < target:
            yield From(asyncio.sleep(1))


    @asyncio.coroutine
    def scheduleAt(self, coro, at):
        """
        Execute a coroutine at a certain time.
        """
        yield From(self.waitUntil(at))
        yield From(coro)


    @asyncio.coroutine
    def recordPass(self, satname):
        """
        Try to record a pass. This will only succeed if no other recording
        is in progress, as only one recorder can access the receiver.
        When the task terminates, a new one is schedules for the next pass.
        """
        sat = self.tledata.get(satname, None)
        if sat is None:
            self.log('Satellite {} not in TLE data anymore'.format(satname))
            return

        self.observer.date = dt.datetime.utcnow()
        p = self.observer.next_pass(sat)
        aos = dt.datetime.strptime(str(p[0]), '%Y/%m/%d %H:%M:%S')
        los = dt.datetime.strptime(str(p[4]), '%Y/%m/%d %H:%M:%S')

        if los < aos:
            aos = dt.datetime.utcnow()

        # Wait until the satellite enters our airspace
        self.log.info('Schedule recording of {} for {}'.format(satname, aos.strftime('%H:%M')))
        yield From(self.waitUntil(aos))

        with (yield From(self.receiverLock)):
            self.log.info('Start recording of {}'.format(satname))
            self.receiver.startRecording(satname)

            while dt.datetime.utcnow() <= los:
                # Calculate the current velocity of the satellite
                self.observer.date = dt.datetime.utcnow()
                sat.compute(self.observer)

                # Calculate the doppler shift
                # See https://github.com/brandon-rhodes/pyephem/issues/34
                vel = -sat.range_velocity * 1.055

                c = 299792458
                sf = math.sqrt((c + vel) / (c - vel))

                frequency = float(self.config[satname]['frequency'])

                shift = frequency * (sf - 1)
                self.receiver.setDopplerShift(shift)

                yield From(asyncio.sleep(10))

            self.log.info('Stop recording of {}'.format(satname))
            self.receiver.stopRecording()

        ts = dt.datetime.utcnow() + dt.timedelta(minutes=3)
        self.testFuture = asyncio.ensure_future(self.scheduleAt(self.recordPass(satname), ts))


    @asyncio.coroutine
    def updateTLE(self):
        """ Download new TLE data and write it to the configuration directory. """
        self.log.info('Updating TLE data')
        try:
            r = urllib2.urlopen('https://celestrak.com/NORAD/elements/weather.txt', timeout=30)
            tledata = r.read()
            with open(os.path.join(self.config.cfgdir, 'satellites.tle'), 'w') as fp:
                fp.write(tledata)

            # Schedule the next update in 24 hours
            ts = dt.datetime.utcnow() + dt.timedelta(days=1)
            asyncio.ensure_future(self.scheduleAt(self.updateTLE(), ts))

        except Exception as e:
            self.log.error(e)
            # Something happened. Schedule another update in 10 minutes
            ts = dt.datetime.utcnow() + dt.timedelta(minutes=10)
            asyncio.ensure_future(self.scheduleAt(self.updateTLE(), ts))

        self.readTLE()


    def readTLE(self):
        """
        Read TLE data from disk and populate the tledata dictionary.
        This also checks if the file really contains TLE data.
        Returns True on success and False on error.
        """
        tlepath = os.path.join(self.config.cfgdir, 'satellites.tle')
        if os.path.exists(tlepath):
            with open(tlepath) as fp:
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

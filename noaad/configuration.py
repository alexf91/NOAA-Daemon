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
import configparser

default = configparser.ConfigParser()
default['General'] = {
        'datadir': os.path.expanduser('~/noaad-data'),
        'saveiq': 0
    }
default['Location'] = {
        'latitude': 0.0,
        'longitude': 0.0,
        'altitude': 0
    }
default['Receiver'] = {
        'sample_rate': 1152000,
        'quad_rate': 96000,
        'audio_rate': 48000,
        'offset': 300000,
        'device_string': 'rtl=0',
        'freq_corr': 0,
    }
default['NOAA 15'] = {
        'frequency': 137.620e6
    }
default['NOAA 18'] = {
        'frequency': 137.9125e6
    }
default['NOAA 19'] = {
        'frequency': 137.100e6
    }

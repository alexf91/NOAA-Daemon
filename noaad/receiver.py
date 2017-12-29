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

import logging
import os
import datetime as dt

from gnuradio import analog
from gnuradio import blocks
from gnuradio import filter
from gnuradio import gr
from gnuradio.filter import firdes

import osmosdr


class Receiver(gr.top_block):
    """
    NOAA receiver flowgraph. All options are static,
    so it's expected that a new instance is created
    for each pass.
    """
    def __init__(self, config):
        gr.top_block.__init__(self)

        self.log = logging.getLogger('Receiver')

        self.samp_rate = int(config['Receiver']['sample_rate'])
        self.quad_rate = int(config['Receiver']['quad_rate'])
        self.audio_rate = int(config['Receiver']['audio_rate'])
        self.offset = float(config['Receiver']['offset'])
        self.center_freq = 137400000
        self.freq_corr = float(config['Receiver']['freq_corr'])
        self.dev_str = str(config['Receiver']['device_string'])

        self.saveiq = bool(int(config['General']['saveiq']))

        self.config = config

        self.filter_sharpness = 3000
        self.filter_bandwidth = 25000

        # Initialize the hardware source
        self.osmosrc = osmosdr.source(self.dev_str)
        self.osmosrc.set_sample_rate(self.samp_rate)
        self.osmosrc.set_center_freq(self.center_freq)
        self.osmosrc.set_bandwidth(self.samp_rate)
        self.osmosrc.set_freq_corr(self.freq_corr)
        self.osmosrc.set_gain_mode(True)

        # Xlating filter
        self.lowpass = firdes.low_pass(1, self.samp_rate, self.filter_bandwidth, self.filter_sharpness)
        self.xlating = filter.freq_xlating_fir_filter_ccc(self.samp_rate // self.quad_rate, self.lowpass, int(self.offset), self.samp_rate)

        # FM demodulator
        #self.demod = analog.fm_demod_cf(
        #        channel_rate=self.quad_rate,
        #        audio_decim=self.quad_rate // self.audio_rate,
        #        deviation=17000,
        #        audio_pass=15000,
        #        audio_stop=16000,
        #        gain=1.0,
        #        tau=0,
        #)
        self.demod = analog.wfm_rcv(
        	quad_rate=self.quad_rate,
        	audio_decimation=self.quad_rate // self.audio_rate,
        )

        # WAV file sink
        self.wavsink = blocks.wavfile_sink('/dev/null', 1, self.audio_rate, 16)

        # Debug file sink needs to be created every time, so we only create it
        # where it's actually needed.
        self.iqsink = None

        # Connect everything
        self.connect((self.osmosrc, 0), (self.xlating, 0))
        self.connect((self.xlating, 0), (self.demod, 0))
        self.connect((self.demod, 0), (self.wavsink, 0))


    def startRecording(self, satname):
        """ Start recording to a new file """
        self.center_freq = float(self.config[satname]['frequency']) - self.offset
        self.osmosrc.set_center_freq(self.center_freq)

        now = dt.datetime.utcnow()

        fname = '{}_{}.wav'.format(satname.replace(' ', '_'), now.strftime('%Y-%m-%d_%H:%M'))
        wavpath = os.path.join(self.config['General']['datadir'], fname).encode()
        self.wavsink.open(wavpath)

        if self.saveiq:
            dname = 'noaad_{}_{}.raw'.format(now.strftime('%Y%m%d_%H%M%S'), self.samp_rate)
            iqpath = os.path.join(self.config['General']['datadir'], dname).encode()
            self.iqsink = blocks.file_sink(gr.sizeof_gr_complex, iqpath, False)
            self.connect((self.osmosrc, 0), (self.iqsink, 0))

        self.start()


    def stopRecording(self):
        """ Finalize an output file """
        self.stop()
        self.wait()
        self.wavsink.close()

        if self.saveiq:
            self.disconnect(self.osmosrc)


    def setDopplerShift(self, f):
        """ Set the Doppler shift in Hz.  """
        self.log.info('Setting offset to {} Hz'.format(self.offset + f))
        self.log.info('Receiving at {} Hz'.format(self.center_freq + self.offset + f))
        self.xlating.set_center_freq(self.offset + f)

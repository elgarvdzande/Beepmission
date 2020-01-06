import enum
import math

import numpy as np


class FrequencySet(enum.Enum):
    SEND = 0
    RECV = 1


class TransmissionParameters:
    def __init__(self):
        self.__base_freq = 2000.0
        self.__is_master = True
        self.__max_payload_size = 12
        self.__num_channels = 8
        self.__sample_rate = 44100
        self.__seq_max = 3
        self.__window_length = 0.1


    def set_window_length(self, window_length):
        self.__window_length = window_length


    def get_window_length(self):
        return self.__window_length


    def set_sample_rate(self, sample_rate):
        self.__sample_rate = sample_rate


    def get_sample_rate(self):
        return self.__sample_rate



    def get_timeout(self):
        # estimate of a resonable timeout, assume START_SEQ len == 1 and header len == 3
        latency = 3.0
        nchannels = self.__num_channels / 2
        data_time_ch = self.__seq_max * 9 * (self.__max_payload_size + 3) / nchannels
        timeout = self.__window_length * (11 + data_time_ch)
        return max(1.5 * timeout, 1.0) + latency


    def set_is_master(self, is_master):
        self.__is_master = is_master


    def get_is_master(self):
        return self.__is_master


    def set_base_freq(self, freq):
        self.__base_freq = freq


    def get_base_freq(self):
        return self.__base_freq


    def set_num_channels(self, num_channels):
        self.__num_channels = num_channels


    def get_num_channels(self):
        return self.__num_channels


    def get_frequencies(self, freq_set):
        factor = np.arange(self.__num_channels) * 0.2 + 1.0
        frequencies = factor * self.__base_freq

        if (self.__is_master and freq_set == FrequencySet.SEND) or \
                (not self.__is_master and freq_set == FrequencySet.RECV):
            return frequencies[0::2]
        else:
            return frequencies[1::2]


    def get_max_bps(self):
        if self.__is_master:
            nchannels = math.ceil(self.__num_channels / 2)
        else:
            nchannels = math.floor(self.__num_channels / 2)

        transmission_time = (11 + math.ceil(9 * (self.__max_payload_size + 3) / nchannels)) * self.__window_length
        return 8 * (self.__max_payload_size - 1) / transmission_time


    def get_window_size(self):
        return round(self.__sample_rate * self.__window_length)


    def set_seq_max(self, seq_max):
        self.__seq_max = seq_max


    def get_seq_max(self):
        return self.__seq_max


    def set_max_payload_size(self, max_payload_size):
        self.__max_payload_size = max_payload_size


    def get_max_payload_size(self):
        return self.__max_payload_size


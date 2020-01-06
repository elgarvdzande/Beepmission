import enum
import threading
import math

import numpy as np

from transmission_parameters import FrequencySet

START_SEQ = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0]

def redundancy_check16(data):
    data = data[:]
    if len(data) % 2 != 0:
        data += b'\x00'

    s = 0x555b
    cursor = 0
    while cursor < len(data):
        s += (data[cursor] << 8) | data[cursor + 1]
        s &= 0xffff
        cursor += 2
    return (0x10000 - s) & 0xffff


def parity(byte):
    assert len(byte) == 8

    # also insert a one after 8 zeros to force a transition
    if np.array_equal(byte, 8 * [0]):
        return 1
    else:
        return np.sum(byte, dtype='int') % 2


def add_parity_bits(bin_data):
    new_bin_data = []
    cursor = 0
    while cursor < len(bin_data):
        offset = min(8, len(bin_data) - cursor)
        chunck = bin_data[cursor:cursor + offset]
        new_bin_data += chunck
        if offset == 8:
            new_bin_data += [parity(chunck)]
        cursor += 8
    return new_bin_data

def remove_parity_bits(bin_data):
    new_bin_data = []
    for i, bit in enumerate(bin_data):
        if i > 0 and (i + 1) % 9 == 0:
            continue
        new_bin_data.append(bit)
    return new_bin_data


class MessageEncoder:
    def __init__(self, params):
        self.__params = params


    def __ifourier(self, ch, bin_data):
        window_size = self.__params.get_window_size()
        sample_rate = self.__params.get_sample_rate()
        freq = self.__params.get_frequencies(FrequencySet.SEND)[ch]

        size = len(bin_data) * window_size
        t = np.arange(size) / sample_rate
        carrier_data = np.cos(2 * np.pi * freq * t, dtype='float32')
        mask = np.empty((0,), dtype='float32')
        for d in bin_data:
            mask = np.hstack([mask, np.full(window_size, d, dtype='float32')])
        return mask * carrier_data


    def __to_bin_data(self, data):
        bin_data = []
        for byte in data:
            bin_data += map(int, '{:08b}'.format(byte))
        return bin_data


    def encode(self, message):
        assert len(message) < 256

        header = [0, 0, len(message)]
        chk_sum = redundancy_check16(bytes(header) + message)
        header[0] = (chk_sum >> 8) & 0xff
        header[1] = chk_sum & 0xff
        complete_message = bytes(header) + message

        frequencies = self.__params.get_frequencies(FrequencySet.SEND)
        nchannels = len(frequencies)
        bin_data = self.__to_bin_data(complete_message)
        bin_data += bytes(-len(bin_data) % nchannels)

        bin_data_ch = [START_SEQ[:] for _ in range(nchannels)]
        for ch, _ in enumerate(frequencies):
            ch_data = bin_data[ch::nchannels]
            bin_data_ch[ch] += add_parity_bits(ch_data)

        audio_data = self.__ifourier(0, bin_data_ch[0])
        for ch in range(1, nchannels):
            audio_data += self.__ifourier(ch, bin_data_ch[ch])

        # normalize audio
        max_value = np.max(np.abs(audio_data))
        audio_data /= max_value

        return audio_data


class MessageDecoder(threading.Thread):
    def __init__(self, params):
        threading.Thread.__init__(self)
        self.__running = True

        self.__params = params
        self.__buffer = np.empty((0,), dtype='float32')
        self.__buffer_lock = threading.Condition()
        self.__decode_buffer = np.empty((0,), dtype='float32')
        self.__messages = []
        self.__messages_lock = threading.Lock()

        # initialize constant sin and cos measurement functions
        # used for calculating the discrete Fourier coefficients
        frequencies = self.__params.get_frequencies(FrequencySet.RECV)
        self.__ch_sin = len(frequencies) * [None]
        self.__ch_cos = len(frequencies) * [None]

        window_size = self.__params.get_window_size()
        sample_rate = self.__params.get_sample_rate()
        t = np.arange(window_size) / sample_rate
        for ch, freq in enumerate(frequencies):
            self.__ch_sin[ch] = np.sin(2 * np.pi * freq * t)
            self.__ch_cos[ch] = np.cos(2 * np.pi * freq * t)


    def __fourier(self, ch, audio):
        window_size = self.__params.get_window_size()

        assert len(audio) % self.__params.get_window_size() == 0

        # we should divide multiply by dt, and then divide by the sum of
        # sin(t) and cos(t), however as this is just a constant do not really
        # care for this. However, as a side effect the fourier constants are
        # not scaled correctly.
        fbin_data = []
        for window in audio.reshape((-1, window_size)):
            a = np.sum(self.__ch_sin[ch] * window)
            b = np.sum(self.__ch_cos[ch] * window)
            fbin_data.append(np.sqrt(a**2 + b**2))

        assert len(fbin_data) == len(audio) // window_size

        return fbin_data


    # length is the payload length (i.e., excluding the 3 header bytes but not the 1 sliding window byte)
    def __calc_message_size(self, length, freq_set):
        window_size = self.__params.get_window_size()
        frequencies = self.__params.get_frequencies(freq_set)

        channel_size = math.ceil(8 * (length + 3) / len(frequencies))
        channel_size += channel_size // 8
        return window_size * (len(START_SEQ) + channel_size)


    def __find_start(self, data):
        window_size = self.__params.get_window_size()

        start_seq_size = len(START_SEQ) * window_size
        step_size = window_size // 4

        cursor = 0
        while cursor + start_seq_size <= len(data):
            fbin_data = self.__fourier(0, data[cursor:cursor + start_seq_size])
            threshold = (fbin_data[0] + fbin_data[1]) / 2
            bin_data = np.array(fbin_data > threshold, dtype='int')
            if np.array_equal(bin_data, START_SEQ):
                return cursor
            cursor += step_size
        return -1


    def __process_message(self, audio_data):
        window_size = self.__params.get_window_size()
        max_payload_size = self.__params.get_max_payload_size()

        # this will speed up decoding, and align force a multiple of window_size frames
        new_size = len(audio_data) - len(audio_data) % window_size
        max_size = self.__calc_message_size(max_payload_size, FrequencySet.RECV)
        audio_data = audio_data[:min(new_size, max_size)]

        frequencies = self.__params.get_frequencies(FrequencySet.RECV)
        bin_data_ch = [[] for _ in range(len(frequencies))]
        for ch, _ in enumerate(frequencies):
            fbin_data = self.__fourier(ch, audio_data)
            min_value = fbin_data[0]
            max_value = fbin_data[1]
            for value in fbin_data:
                threshold = (min_value + max_value) / 2
                if value > threshold:
                    bin_data_ch[ch].append(1)
                    max_value = value
                else:
                    bin_data_ch[ch].append(0)
                    min_value = value

        # drop start seq and parity bits
        for channel, _ in enumerate(frequencies):
            no_start_seq = bin_data_ch[channel][len(START_SEQ):]
            bin_data_ch[channel] = remove_parity_bits(no_start_seq)

        # recreate the original bit stream
        bin_data = []
        for i in range(len(bin_data_ch[0])):
            for channel, _ in enumerate(frequencies):
                bin_data.append(bin_data_ch[channel][i])

        # convert bit steam to bytes object
        data = b''
        cursor = 0
        while cursor + 8 <= len(bin_data):
            byte = bin_data[cursor:cursor + 8]
            bit_string = ''.join(map(str, byte))
            data += bytes([int(bit_string, 2)])
            cursor += 8

        # length of the payload
        length = data[2] & 0x3f
        if length + 3 > len(data):
            # there is not enough data to recv the message (e.g., length is invalidated during transmission)
            return -1

        # do the `normal' parity check
        data = data[:length + 3]
        if redundancy_check16(data) != 0:
            return -1

        # drop header containing redundancy check and length (3 byte)
        message = data[3:]

        # TODO: we can check parity bits however, this tured out to be quite a difficult/ugly task

        print(f'recved: {message}')

        with self.__messages_lock:
            self.__messages.append(message)

        return self.__calc_message_size(len(message), FrequencySet.RECV)


    def __process(self):
        window_size = self.__params.get_window_size()
        max_required = self.__calc_message_size(self.__params.get_max_payload_size(), FrequencySet.RECV)

        cursor = 0
        while cursor + max_required <= len(self.__decode_buffer):
            offset = self.__find_start(self.__decode_buffer[cursor:])
            if offset == -1:
                # no start sequence found, drop entire buffer
                return len(self.__decode_buffer)
            cursor += offset

            if cursor + max_required > len(self.__decode_buffer):
                # we found start sequence, however there is not enough data
                # to decode the packet. Hence, return and wait for more data
                return cursor


            size = self.__process_message(self.__decode_buffer[cursor:])
            if size == -1:
                # failed to process packet, increase cursor slightly and try again
                size = max(1, window_size // 10)
            cursor += size
        return cursor


    # block until either 1) data is received or when the thread is stopped
    def __wait_for_data(self):
        new_data = np.empty((0,), dtype='float32')
        with self.__buffer_lock:
            while len(self.__buffer) == 0:
                self.__buffer_lock.wait()
                if not self.__running:
                    return new_data
            new_data = self.__buffer
            self.__buffer = np.empty((0,), dtype='float32')
        return new_data


    def run(self):
        while self.__running:
            new_data = self.__wait_for_data()
            self.__decode_buffer = np.hstack([self.__decode_buffer, new_data])

            processed = self.__process()
            self.__decode_buffer = self.__decode_buffer[processed:]

            max_size = self.__calc_message_size(self.__params.get_max_payload_size(), FrequencySet.RECV)
            if len(self.__decode_buffer) > max_size:
                print('buffer is too large')
                self.__decode_buffer = self.__decode_buffer[:-2 * max_size]


    def add_frames(self, frames):
        with self.__buffer_lock:
            self.__buffer = np.hstack([self.__buffer, frames])
            self.__buffer_lock.notify()


    def get_message(self):
        message = None
        with self.__messages_lock:
            if self.__messages:
                message = self.__messages[0]
                self.__messages = self.__messages[1:]
        return message


    def stop(self):
        self.__running = False
        with self.__buffer_lock:
            self.__buffer_lock.notify()
        self.join()


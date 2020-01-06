import time
import math

import numpy as np

from message_protocol import MessageDecoder
from message_protocol import MessageEncoder
from transmission_parameters import FrequencySet
from audio_stream import AudioStream


class SlidingWindow:
    def __init__(self, params):
        self.__params = params

        self.__send_buffer = b''
        self.__send_frames = (self.__params.get_seq_max() + 1) * [None]
        self.__send_ack = 0
        self.__send_seq = 0
        self.__timeout = 0

        self.__recv_buffer = b''
        self.__recv_seq = 0

        self.__message_decoder = MessageDecoder(self.__params)
        self.__message_encoder = MessageEncoder(self.__params)
        self.__message_decoder.start()

        self.__audio_stream = AudioStream(self.__params)
        self.__audio_stream.start()

        self.__on_send_complete = lambda: None
        self.__on_data_available = lambda: None

        # DEBUG:
        print(f'sending freq set: {self.__params.get_frequencies(FrequencySet.SEND)}')
        print(f'recving freq set: {self.__params.get_frequencies(FrequencySet.RECV)}')


    def __send_ack_message(self):
        print(f'send_ack_message {self.__recv_seq}')
        header = 0x00
        header |= 0x80
        header |= 0x40 if self.__params.get_is_master() else 0x00
        message = bytes([header | self.__recv_seq])

        audio_data = self.__message_encoder.encode(message)
        self.__audio_stream.play(audio_data)


    def __send_data_message(self):
        max_payload_size = self.__params.get_max_payload_size()
        data_available = len(self.__send_buffer)

        header = 0x00
        header |= 0x40 if self.__params.get_is_master() else 0x00
        header |= self.__send_seq

        message_size = min(data_available, max_payload_size - 1)
        message = bytes([header]) + self.__send_buffer[:message_size]
        self.__send_buffer = self.__send_buffer[message_size:]

        # save message such that it can be resent later if a timeout occurs
        self.__send_frames[self.__send_seq] = message

        audio_data = self.__message_encoder.encode(message)
        self.__audio_stream.play(audio_data)
        print(f'send_data_message {message}')


    def __resend_data_message(self, seq):
        message = self.__send_frames[seq]
        print(f'resend_data_message {message}')

        audio_data = self.__message_encoder.encode(message)
        self.__audio_stream.play(audio_data)


    def attach_on_send_complete(self, func):
        self.__on_send_complete = func


    def attach_on_data_availbale(self, func):
        self.__on_data_available = func


    # send data, returns immediately.
    def send(self, data):
        self.__send_buffer += data


    # try to receive data, returns a byte array of size >= 0
    def recv(self):
        data = self.__recv_buffer
        self.__recv_buffer = b''
        return data


    # stop and close connection
    def stop(self):
        self.__message_decoder.stop()
        self.__audio_stream.stop()
        print('called stop on sliding window object')


    # because this is a polling based system, this object required periodic updates
    # to process the data, call this methods around 10 times a second
    def tick(self):
        recv_data = self.__audio_stream.record()
        self.__message_decoder.add_frames(recv_data)

        window_size = self.__params.get_seq_max()
        # note this is NOT the same window size in the en/decoder
        # methods, rather it is the max number of frames in the
        # Go Back N protocol
        while True:
            message = self.__message_decoder.get_message()
            if message is None:
                break
            if len(message) == 0:
                print('Received empty message, this should not happen')
                continue

            # Go Back N (sliding window) status
            status = message[0]
            ack = bool(status & 0x80)
            is_master = bool(status & 0x40)
            seq = status & 0x0f

            if is_master == self.__params.get_is_master():
                # we trigged on our own message, this can happen
                # if there is a low noise level and a small amount
                # of energy carries over to another band
                print('trigged on my own message')
                continue

            if ack:
                # we received a acknowledgement
                self.__send_ack = seq
                if self.__send_ack == self.__send_seq and not self.__send_buffer:
                    self.__on_send_complete()
            else:
                # we received a new data frame
                if self.__recv_seq == seq:
                    self.__recv_buffer += message[1:]
                    self.__recv_seq = (self.__recv_seq + 1) % (self.__params.get_seq_max() + 1)
                self.__send_ack_message()
                self.__on_data_available()

        # Try to send some data, if available
        while self.__send_buffer:
            # check if we can send (i.e., 1 or more frames had been acknowledged or not
            # window_size frames have been send yet).
            diff = (self.__send_seq - self.__send_ack) % (window_size + 1)
            if window_size - diff <= 0:
                break

            self.__send_data_message()
            self.__send_seq = (self.__send_seq + 1) % (window_size + 1)
            self.__timeout = time.time() + self.__params.get_timeout()

        if time.time() > self.__timeout:
            start = self.__send_ack
            end = self.__send_seq
            while (end - start) % (window_size + 1) != 0:
                self.__resend_data_message(start)
                start = (start + 1) % (window_size + 1)
            self.__timeout = time.time() + self.__params.get_timeout()


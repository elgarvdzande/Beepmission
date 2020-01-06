#!/usr/bin/python

import random
import time
import sys

import numpy as np
import matplotlib.pyplot as plt

sys.path.append('..')
from message_protocol import MessageEncoder
from message_protocol import MessageDecoder
from transmission_parameters import TransmissionParameters
from transmission_parameters import FrequencySet


def test_simple():
    params_send = TransmissionParameters()
    params_send.set_num_channels(2)

    params_recv = TransmissionParameters()
    params_recv.set_num_channels(2)
    params_recv.set_is_master(False)

    encoder = MessageEncoder(params_send)
    decoder = MessageDecoder(params_recv)
    decoder.start()

    org_data = b'Hello World'

    l = []
    l.append(encoder.encode(org_data))
    l.append(np.zeros(1000000, dtype='float32'))
    l.append(encoder.encode(org_data))
    l.append(np.zeros(1000000, dtype='float32'))
    audio_data = np.hstack(l)

    decoder.add_frames(audio_data)
    time.sleep(10)
    recv_data0 = decoder.get_message()
    recv_data1 = decoder.get_message()

    decoder.stop()

    if org_data != recv_data0 or org_data != recv_data1:
        print('test_simple failed')
        print(recv_data0)
        print(recv_data1)
    else:
        print('test_simple success')


def test_simple_mul_ch():
    params_send = TransmissionParameters()
    params_send.set_num_channels(16)

    params_recv = TransmissionParameters()
    params_recv.set_num_channels(16)
    params_recv.set_is_master(False)

    encoder = MessageEncoder(params_send)
    decoder = MessageDecoder(params_recv)
    decoder.start()

    org_data = b'Hello World'

    l = []
    l.append(encoder.encode(org_data))
    l.append(encoder.encode(org_data))
    l.append(np.zeros(1000000, dtype='float32'))
    audio_data = np.hstack(l)

    decoder.add_frames(audio_data)
    time.sleep(5)
    recv_data0 = decoder.get_message()
    recv_data1 = decoder.get_message()

    decoder.stop()

    if org_data != recv_data0 or org_data != recv_data1:
        print('test_simple_mul_ch failed')
        print(recv_data0)
        print(recv_data1)
    else:
        print('test_simple_mul_ch success')


def test_simple_empty():
    params_send = TransmissionParameters()
    params_send.set_num_channels(16)

    params_recv = TransmissionParameters()
    params_recv.set_num_channels(16)
    params_recv.set_is_master(False)

    encoder = MessageEncoder(params_send)
    decoder = MessageDecoder(params_recv)
    decoder.start()

    org_data = b''

    l = []
    l.append(encoder.encode(org_data))
    l.append(encoder.encode(org_data))
    l.append(np.zeros(1000000, dtype='float32'))
    audio_data = np.hstack(l)

    decoder.add_frames(audio_data)
    time.sleep(5)
    recv_data0 = decoder.get_message()
    recv_data1 = decoder.get_message()

    decoder.stop()

    if org_data != recv_data0 or org_data != recv_data1:
        print('test_simple_empty failed')
        print(recv_data0)
        print(recv_data1)
    else:
        print('test_simple_empty success')


def test_simple_full():
    params_send = TransmissionParameters()
    params_send.set_num_channels(16)

    params_recv = TransmissionParameters()
    params_recv.set_num_channels(16)
    params_recv.set_is_master(False)

    encoder = MessageEncoder(params_send)
    decoder = MessageDecoder(params_recv)
    decoder.start()

    org_data = b'a' * params_send.get_max_payload_size()

    l = []
    l.append(encoder.encode(org_data))
    l.append(encoder.encode(org_data))
    l.append(np.zeros(1000000, dtype='float32'))
    audio_data = np.hstack(l)

    decoder.add_frames(audio_data)
    time.sleep(5)
    recv_data0 = decoder.get_message()
    recv_data1 = decoder.get_message()

    decoder.stop()

    if org_data != recv_data0 or org_data != recv_data1:
        print('test_simple_full failed')
        print(recv_data0)
        print(recv_data1)
    else:
        print('test_simple_full success')


def test_redundancy():
    from message_protocol import redundancy_check16

    for length in range(100):
        d = bytes([random.randint(0, 255) for _ in range(length)])
        chk_sum = redundancy_check16(bytes(2) + d)
        l = [0, 0]
        l[0] = chk_sum >> 8
        l[1] = chk_sum & 0xff
        if redundancy_check16(bytes(l) + d) != 0:
            print('test_redundancy failed')
            return
    print('test_redundancy success')


def test_parity():
    from message_protocol import add_parity_bits
    from message_protocol import remove_parity_bits

    for length in range(100):
        orig = [random.randint(0, 1) for _ in range(length)]
        if orig != remove_parity_bits(add_parity_bits(orig)):
            print('test_parity failed')
            print(cursor)
            return
    print('test_parity success')


def test_message_legnth_calc():
    print('test_message_legnth_calc is slow')
    for ch in range(1, 17):
        params_send = TransmissionParameters()
        params_send.set_num_channels(ch)

        params_recv = TransmissionParameters()
        params_recv.set_num_channels(ch)
        params_recv.set_is_master(False)

        encoder = MessageEncoder(params_send)
        decoder = MessageDecoder(params_recv)

        for length in range(0, 63):
            orig = bytes([random.randint(0, 255) for _ in range(length)])
            true_length = len(encoder.encode(orig))
            calc_length= decoder._MessageDecoder__calc_message_size(len(orig), FrequencySet.RECV)

            if calc_length != true_length:
                print('test_message_legnth_calc failed')
                print(f'{ch=} {length=} {true_length=} {calc_length=}')
                return
    print('test_message_legnth_calc success')


def test_simple_no_pad():
    params_send = TransmissionParameters()
    params_send.set_num_channels(16)

    params_recv = TransmissionParameters()
    params_recv.set_num_channels(16)
    params_recv.set_is_master(False)

    encoder = MessageEncoder(params_send)
    decoder = MessageDecoder(params_recv)
    decoder.start()

    org_data = b'a' * params_send.get_max_payload_size()

    l = []
    l.append(encoder.encode(org_data))
    audio_data = np.hstack(l)

    decoder.add_frames(audio_data)
    time.sleep(5)
    recv_data0 = decoder.get_message()

    decoder.stop()

    if org_data != recv_data0:
        print('test_simple_no_pad failed')
        print(recv_data0)
    else:
        print('test_simple_no_pad success')


def test_segmented_no_pad():
    params_send = TransmissionParameters()
    params_send.set_num_channels(16)

    params_recv = TransmissionParameters()
    params_recv.set_num_channels(16)
    params_recv.set_is_master(False)

    encoder = MessageEncoder(params_send)
    decoder = MessageDecoder(params_recv)
    decoder.start()

    org_data = b'a' * params_send.get_max_payload_size()

    l = []
    l.append(encoder.encode(org_data))
    audio_data = np.hstack(l)

    unit_test_test = np.empty((0,), dtype='float32')
    for i in range(0, len(audio_data), 1000):
        decoder.add_frames(audio_data[i:i+1000])
        unit_test_test = np.hstack([unit_test_test, audio_data[i:i+1000]])
    if not np.array_equal(unit_test_test, audio_data):
        print('arrays are not equal, this should not happen')
        print(len(unit_test_test))
        print(len(audio_data))

    time.sleep(5)
    recv_data0 = decoder.get_message()

    decoder.stop()

    if org_data != recv_data0:
        print('test_segmented_no_pad failed')
        print(recv_data0)
    else:
        print('test_segmented_no_pad success')


def test_segmented_pad():
    params_send = TransmissionParameters()
    params_send.set_num_channels(16)

    params_recv = TransmissionParameters()
    params_recv.set_num_channels(16)
    params_recv.set_is_master(False)

    encoder = MessageEncoder(params_send)
    decoder = MessageDecoder(params_recv)
    decoder.start()

    org_data = b'a' * params_send.get_max_payload_size()

    l = []
    l.append(np.zeros(12672, dtype='float32'))
    l.append(encoder.encode(org_data))
    l.append(np.zeros(16672, dtype='float32'))
    audio_data = np.hstack(l)

    unit_test_test = np.empty((0,), dtype='float32')
    for i in range(0, len(audio_data), 1000):
        decoder.add_frames(audio_data[i:i+1000])
        unit_test_test = np.hstack([unit_test_test, audio_data[i:i+1000]])

    if not np.array_equal(unit_test_test, audio_data):
        print('arrays are not equal, this should not happen')
        print(len(unit_test_test))
        print(len(audio_data))

    time.sleep(5)
    recv_data0 = decoder.get_message()

    decoder.stop()

    if org_data != recv_data0:
        print('test_segmented_pad failed')
        print(recv_data0)
    else:
        print('test_segmented_pad success')

if __name__ == '__main__':
    test_segmented_pad()
    test_segmented_no_pad()
    test_simple_no_pad()
    test_parity()
    test_redundancy()
    test_simple()
    test_simple_mul_ch()
    test_simple_empty()
    test_simple_full()
    test_message_legnth_calc()



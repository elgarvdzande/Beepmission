import time
import threading

import sounddevice as sd
import numpy as np


MAX_RECV_BUF_SIZE = 1024 * 1024 # 1 MiB


class AudioStream(threading.Thread):
    def __init__(self, params):
        threading.Thread.__init__(self)
        sample_rate = params.get_sample_rate()
        block_size = sample_rate // 20
        #block_size = 0
        self.__stream = sd.Stream(samplerate = sample_rate, blocksize = block_size,
                latency = 'high', channels = 1, dtype='float32')

        self.__running = True
        self.__lock = threading.Lock()
        self.__send_buf = np.empty((0,), dtype='float32')
        self.__recv_buf = np.empty((0,), dtype='float32')
        self.__is_dropping = False


    def run(self):
        self.__stream.start()
        while self.__running:
            # read frames
            nframes = self.__stream.read_available
            frames = self.__stream.read(nframes)[0][:,0]
            with self.__lock:
                self.__recv_buf = np.hstack([self.__recv_buf, frames])
                if len(self.__recv_buf) > MAX_RECV_BUF_SIZE:
                    self.__recv_buf[:MAX_RECV_BUF_SIZE]
                    if self.__is_dropping == False:
                        print('Warning dropping recv buffer content')
                    self.__is_dropping = True
                else:
                    self.__is_dropping = False

            # write frames
            nframes = self.__stream.write_available
            frames = None
            with self.__lock:
                nframes_buf = np.min([len(self.__send_buf), nframes])
                nframes_zero = np.max([0, nframes - nframes_buf])
                frames = np.hstack([self.__send_buf[:nframes_buf],
                    np.zeros(nframes_zero, dtype='float32')])
                self.__send_buf = self.__send_buf[nframes_buf:]
            self.__stream.write(frames)

            time.sleep(.01)
        self.__stream.stop()


    def stop(self):
        self.__running = False
        self.join()


    def play(self, frames):
        with self.__lock:
            self.__send_buf = np.hstack([self.__send_buf, frames])


    def record(self):
        data = None
        with self.__lock:
            data = self.__recv_buf
            self.__recv_buf = np.empty((0,), dtype='float32')
        return data


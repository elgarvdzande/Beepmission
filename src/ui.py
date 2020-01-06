#!/usr/bin/python3

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gtk
from gi.repository import GLib

from transmission_parameters import FrequencySet
from transmission_parameters import TransmissionParameters
from sliding_window import SlidingWindow

MESSAGE_INPUT_ACTIVE = 'Start typing your message'
MESSAGE_INPUT_DISABLED = 'Message input is disabled'
MESSAGE_INPUT_SENDING = 'Sending message, input disabled'

class MainWindow:
    def __init__(self, ui_file):
        builder = Gtk.Builder()
        builder.add_from_file(ui_file)
        builder.connect_signals(self)

        self.__builder = builder
        self.__activate_switch  = builder.get_object('activate_switch')
        self.__base_frequency   = builder.get_object('base_frequency')
        self.__max_payload_size = builder.get_object('max_payload_size')
        self.__max_windows      = builder.get_object('max_windows')
        self.__message_box      = builder.get_object('message_box')
        self.__mode_selector    = builder.get_object('mode_selector')
        self.__num_channels     = builder.get_object('num_channels')
        self.__sample_rate      = builder.get_object('sample_rate')
        self.__send             = builder.get_object('send')
        self.__window           = builder.get_object('window')
        self.__window_length    = builder.get_object('window_length')
        self.__timeout          = builder.get_object('timeout')
        self.__headerbar        = builder.get_object('headerbar')
        self.__message_history  = builder.get_object('message_history')

        self.__window.show_all()
        self.__params = None
        self.__resetting = False

        self.__set_default()

        self.__sliding_window = None
        GLib.timeout_add(100, self.on_stream_tick)

        self.__partial_message = ''


    def __enable_settings(self, state):
        self.__base_frequency.set_sensitive(state)
        self.__max_payload_size.set_sensitive(state)
        self.__max_windows.set_sensitive(state)
        self.__mode_selector.set_sensitive(state)
        self.__num_channels.set_sensitive(state)
        self.__sample_rate.set_sensitive(state)
        self.__window_length.set_sensitive(state)

        self.__message_box.set_sensitive(not state)
        if state:
            self.__message_box.set_text('')
            self.__message_box.set_placeholder_text(MESSAGE_INPUT_DISABLED)
        else:
            self.__message_box.set_placeholder_text(MESSAGE_INPUT_ACTIVE)

        #send is always disabled, if we leave setup mode because the text entry is empty
        self.__send.set_sensitive(False)


    def __update_subtitle(self):
        self.__headerbar.set_subtitle('Biterate: ~{:.1f} bps'.format(self.__params.get_max_bps()))


    def __set_default(self):
        self.__activate_switch.set_active(False)
        self.__enable_settings(True)

        self.__params = TransmissionParameters()

        self.__resetting = True
        self.__base_frequency.set_value(self.__params.get_base_freq())
        self.__max_windows.set_value(self.__params.get_seq_max())
        self.__max_payload_size.set_value(self.__params.get_max_payload_size())
        self.__num_channels.set_value(self.__params.get_num_channels())
        self.__sample_rate.set_value(self.__params.get_sample_rate() / 1000)
        self.__window_length.set_value(self.__params.get_window_length())
        self.__mode_selector.set_active(not self.__params.get_is_master())
        self.__timeout.set_text('{:.1f}'.format(self.__params.get_timeout()))
        self.__update_subtitle()
        self.__resetting = False


    def __add_message(self, msg):
        it = self.__message_history.get_end_iter()
        self.__message_history.insert(it, msg)


    def on_send_complete(self):
        self.__message_box.set_sensitive(True)
        self.__message_box.set_placeholder_text(MESSAGE_INPUT_ACTIVE)


    def on_data_available(self):
        data = self.__sliding_window.recv()
        self.__partial_message += data.decode('ascii')
        if self.__partial_message.endswith('\n'):
            self.__add_message('< ' + self.__partial_message)
            self.__partial_message = ''


    def on_stream_tick(self):
        if self.__sliding_window:
            self.__sliding_window.tick()

        return True


    def on_destroy(self, widget):
        if self.__sliding_window:
            self.__sliding_window.stop()
            self.__sliding_window = None
        Gtk.main_quit()


    def on_update_parameters(self, widget):
        if self.__resetting:
            return
        self.__params.set_base_freq(self.__base_frequency.get_value())
        self.__params.set_seq_max(self.__max_windows.get_value_as_int())
        self.__params.set_max_payload_size(self.__max_payload_size.get_value_as_int())
        self.__params.set_num_channels(self.__num_channels.get_value_as_int())
        self.__params.set_sample_rate(round(self.__sample_rate.get_value() * 1000))
        self.__params.set_window_length(self.__window_length.get_value())
        self.__params.set_is_master(not self.__mode_selector.get_active())

        self.__update_subtitle()
        self.__timeout.set_text('{:.1f}'.format(self.__params.get_timeout()))


    def on_activate(self, widget, state):
        if state:
            self.__enable_settings(False)
            self.__sliding_window = SlidingWindow(self.__params)
            self.__sliding_window.attach_on_send_complete(self.on_send_complete)
            self.__sliding_window.attach_on_data_availbale(self.on_data_available)
        else:
            self.__enable_settings(True)
            self.__sliding_window.stop()
            self.__sliding_window = None


    def on_reset(self, widget):
        self.__set_default()


    def on_mode_switch(self, widget):
        if self.__mode_selector.get_active():
            self.__mode_selector.set_label('Slave')
        else:
            self.__mode_selector.set_label('Master')
        self.on_update_parameters(None)


    def on_text_entry_change(self, widget):
        if self.__message_box.get_text() == '':
            self.__send.set_sensitive(False)
        else:
            self.__send.set_sensitive(True)


    def on_send(self, widget):
        message = self.__message_box.get_text()
        message += '\n'

        self.__add_message('> ' + message)

        self.__message_box.set_text('')
        self.__message_box.set_sensitive(False)
        self.__message_box.set_placeholder_text(MESSAGE_INPUT_SENDING)
        self.__sliding_window.send(message.encode('ascii'))


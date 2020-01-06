#!/usr/bin/python3

import sys
import os
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ui import MainWindow

def main():
    ui_file = os.path.realpath(os.path.dirname(sys.argv[0])) + '/ui.glade'

    main_window = MainWindow(ui_file)
    Gtk.main()

if __name__ == '__main__':
    main()

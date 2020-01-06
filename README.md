# Beepmission
A trough air data transmission application

# Description
Beepmission is an application to transmit data using inexpensive audio hardware. By utilizing multiple frequency encoding and Go-Back-N ARQ, we achieve a fast, full duplex and errorless connection. We also provide graphical user interface to show the capabilities of our implemen- tation. We built the back end as a separate library, which makes it independent of the GUI. Because of this, the library can easily be adopted to be used in a different setting.

A more in depth  description can be found in the report.pdf file

# How to run (Ubuntu)
    $ cd Beepmission/src
    $ sudo apt-get install python3-numpy python3-pip libportaudio-ocaml
    $ pip3 install sounddevice
    $ ./main.py

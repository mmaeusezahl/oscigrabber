# oscigrabber - a simple GUI for oscilloscope data transfer

This is a simple, single Python file script that launches a GUI, which can
transfer data from an oscilloscope to the PC and save it a CSV file adding an
optional comment.

Its current scope includes the usage in a physics labcourse.

![Screenhot of the GUI](https://github.com/mmaeusezahl/oscigrabber/blob/master/screenshot/screenshot.png?raw=true)

## Features

* Tested on:
  * *Agilent DSO-X 2002A*
  * *Keysight DSO-X 3024A*
  * ... but it might work on many Agilent/Keysight oscilloscope by just setting
    the correct number of channels in the code
* Supports an full open-source software stack based on
  [pyvisa](https://github.com/pyvisa/pyvisa) and
  [pyvisa-py](https://github.com/pyvisa/pyvisa-py)
  (but also works with NI-VISA on Windows)
* Copies data from the oscilloscope
* Automatically detects the currently active channels on the oscilloscope or
  transfering a user-defined set of channels
* Saves the data to a CSV file with an optional comment
* Already saved datasets can be reviewed
* Somewhat fault tolerant
* Tested on Windows and Linux

## Known Issues

* The oscilloscope will crash if it is digitizing slowly (hard timeout set
  to 25 seconds in the code) or not triggering at all

## Installation

This project was tested to be compatible with Python 3.8 (but should work on
other Python 3 versions). Install it from this GIT repository using

```
pip install git+https://github.com/mmaeusezahl/oscigrabber.git
```

You additionally have to install a wokring VISA backend as explained in the 
[pyvisa](https://github.com/pyvisa/pyvisa) documentation.

## Running

```
python -m oscigrabber 
```

## Feature Ideas and improvements

* Add support for different type of VISA implementations
* Add support for other oscilloscope types and vendors
* Add an option to not call the ``:DIGitize`` command if the oscilloscope is
  already stopped and data is available
* Automatically detect the correct number of channels
* Prevent the oscilloscope from crashing on slow acquisition by detecting it
* Better error detection and handling
* Add a flashy icon

## Background

This project was born out of need to provide a simple and Linux compatible GUI
to transfer data from a *Keysight DSO-X 3024A* oscilloscope and save it as a
CSV file for a physics labcourse. The previous way to use a USB stick for
data transfer is both cumbersome (using the front-panel of the oscilloscope) and
prone to mistakes (saving setup files or screenshots instead of data).
As I could not find any ready solution I came up with this simple interface.

## Related projects

* A tool to interact with Rigol oscilloscopes: [DSRemote](https://gitlab.com/Teuniz/DSRemote)
* A tool to interact with a Hantek USB oscilloscope: [OpenHantek](https://github.com/OpenHantek/openhantek)
* A signal analysis software suite, which has Mixed-Signal-Oscilloscope support for a wide range of devices:
  [sigrok](https://sigrok.org/wiki/Main_Page), in particular the
  [SmuView](https://sigrok.org/wiki/SmuView)

## Contributing

Contributions of any kind are welcome, especially in the form of pull-requests.

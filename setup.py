from setuptools import setup

setup(name='Osci-Grabber',
      version = '0.1',
      description = 'Simple GUI to transfer data from an (Agilent / Keysight) oscilloscope and save it as CSV. ',
      author = 'Max Mäusezahl',
      author_email = 'mmaeusezahl@pi5.physik.uni-stuttgart.de',
      url = 'https://github.com/mmaeusezahl/osci-grabber',
      scripts = ['oscigrabber.py'],
      install_requires = [
          'PyQt6',
          'pyvisa',
          'pyvisa-py',
          'pyqtgraph',
          'pyusb',
          'numpy',
          'pandas'
      ]
     )
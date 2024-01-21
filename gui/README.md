# Parsagon Desktop Application

## Running locally

* Install PyQT in your virtualenv.  You can either run `pip3 install PyQt6==6.6.1` in the main project virtualenv, or switch to using the virtualenv produced by the build instructions below (this virtualenv is located in the `src` directory rather than in the project root).
* `cd` into the `src` directory.
* Run `python3 ./parsagon/gui_entry.py`
* Keep in mind that some environment variables may be overridden if they are specified in `gui_entry.py`.

## Building for MacOS

* Deactivate the virtual environment - a new one will be created for the build.


* Run `gui/build.sh 0`

## Building for Windows

* Using Windows command prompt, `cd` into the root of the repo.
* Run `gui\build.bat 0`
* The output will be located at `gui\ParsagonInstaller.exe`

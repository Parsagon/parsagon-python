# Parsagon Desktop Application

## Running locally

* Activate the venv.
* `cd` into the `src` directory.
* Run `python3 ./parsagon/gui_entry.py`
* Keep in mind that some environment variables may be overridden if they are specified in `gui_entry.py`.

## Building for MacOS

* Deactivate the virtual environment - a new one will be created for the build.

* Using the link https://github.com/txoof/codesign/blob/main/Signing_and_Notarizing_HOWTO.md, 

	* Follow the instructions under `Setup`.  It is undocumented, but you need to create a Cert Signing Request locally on your computer using Keychain and upload it when you create the two certs for App and Installer.
	* Then follow the instructions under `Create an App-Specific password for altool to use`.
	* At the end you should set `APP_HASH` and `INSTALLER_HASH` using the output from `security find-identity -p basic -v`
	* You should also set `DEV_EMAIL` to your Apple ID developer email, and `TEAM_ID` according to the screenshots [here](https://apple.stackexchange.com/a/396723)

* Not that the `API_BASE` environment variable must be hard-coded if you want to build a development version of the app.  Uncomment the line with `os.environ["API_BASE"]` in `gui.py`

* Run `gui/build.sh`

* Wait for an email to your Apple ID email saying that the application has been notarized.

* Run: `xcrun stapler staple ./src/dist/Parsagon.pkg` 

* The pkg file located in `./src/dist` is now notarized.

	

	Other reference

	* https://gist.github.com/txoof/0636835d3cc65245c6288b2374799c43 (more links)
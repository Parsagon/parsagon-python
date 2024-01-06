# Parsagon Desktop Application

**NOTE**: For everything below, you must first set `GUI_ENABLED` to True in `settings.py`!

## Running locally

* Install PyQT in your virtualenv.  You can either run `pip3 install PyQt6==6.6.1` in the main project virtualenv, or switch to using the virtualenv produced by the build instructions below (this virtualenv is located in the `src` directory rather than in the project root).
* `cd` into the `src` directory.
* Run `python3 ./parsagon/gui_entry.py`
* Keep in mind that some environment variables may be overridden if they are specified in `gui_entry.py`.

## Building for MacOS

* Deactivate the virtual environment - a new one will be created for the build.

* Open Keychain Access on your Mac -> Certificate Assistant -> Request a Certificate from a Certificate Authority -> fill out information. Specify "save to disk".

	* Leave the CA Email Address field empty.
	* You will need the resulting file (a "certificate signing request") to get certificates for the app and the installer in the next step.

* Using the link https://github.com/txoof/codesign/blob/main/Signing_and_Notarizing_HOWTO.md, 

  * Follow the instructions under `Setup`.  It should guide you through create two certificates in your Apple developer account (once you have paid): one for the app, one for the installer.  You will have to upload your certificate signing request as part of the process.
  * Then follow the instructions under `Create an App-Specific password for altool to use`.  Save your app-specific password in as the `APP_SPECIFIC_PASSWORD` environment variable.
  * Set `APP_HASH` and `INSTALLER_HASH` environment variables using the output from `security find-identity -p basic -v`
  * You should also set `DEV_EMAIL` to your Apple ID developer email, and `TEAM_ID` according to the screenshots [here](https://apple.stackexchange.com/a/396723)

* We must convert the installer and app certificates into a format usable by Github actions.  If you plan to build only locally you can skip this step.  Follow the instructions below for both the app **AND** installer certificates:

	* Find the full name of the certificate (including team ID) in the output of `security find-identity -p basic -v`. You will need this name in the next step.

	* Generate a secure password - we will call it `$SECURE_PASSWORD`.  In Github actions this should be called `KEYCHAIN_PASSWORD`.

	* Run `security export -t identities -f pkcs12 -k ~/Library/Keychains/login.keychain-db -o AppCert.p12 -P $SECURE_PASSWORD -c NameFromPreviousStep`

	* Encode the resulting p12 file to base64, and save it as a secret for Github actions:

		```
		base64 AppCert.p12 > AppCert_base64.txt
		```

		Copy the contents of the txt file into the `APP_CERT` secret.  For when you repeat these steps for the installer cert, the secret name is `INSTALLER_CERT`.


* Not that the `API_BASE` environment variable must be hard-coded if you want to build a development version of the app.  Uncomment the line with `os.environ["API_BASE"]` in `gui.py`

* Run `gui/build.sh`

* The pkg file located in `./src/dist` is now notarized.

  

  Other reference

  * https://gist.github.com/txoof/0636835d3cc65245c6288b2374799c43 (more links)



## Building for Windows

* Using Windows command prompt, `cd` into the root of the repo.
* Run `gui/build.sh`
* The output will be located at `gui/ParsagonInstaller.exe`



## Known issues

* When enough messages are added, a scroll bar appears on the right.  This causes a slight decrease in the width of the message space, similar to if you had resized the window to be slightly less in width.  This results in a few of the message callouts being too small for their text content and requiring their own scrolling systems, but most are fine.
# Define the name of the installer
!ifndef VERSION
    !define VERSION "Dev"
!endif

OutFile "Parsagon_Installer_v${VERSION}.exe"

# Define the installation directory
InstallDir "$PROGRAMFILES\Parsagon"

Name "Parsagon"

BrandingText " "

# Default installation section
Section "Parsagon Installation"

    # Set output path to the installation directory.
    SetOutPath $INSTDIR

    # Include your executable and other necessary files
    File "..\src\dist\Parsagon.exe"

    # Create a shortcut to the executable
    CreateShortcut "$DESKTOP\Parsagon.lnk" "$INSTDIR\Parsagon.exe"

SectionEnd
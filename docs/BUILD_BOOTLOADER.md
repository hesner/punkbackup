# Building PunkBackup with its own PyInstaller bootloader

Since v1.8.10 the app is packaged with a PyInstaller bootloader compiled on the build
PC, not the stock one that ships in PyInstaller's wheel. The stock bootloader is the
same file in thousands of programs, including malware, so antivirus engines (Avast
among them) flag anything built with it. A locally compiled one is a different file.

This does not make a new, unsigned program "trusted": reputation systems such as
Avast CyberCapture may still check the first launch of each new version. Only a code
signing certificate addresses that.

`PunkBackup.spec` refuses to build with the stock bootloader, so a fresh `.venv` fails
loudly until these steps are repeated.

## Steps (Windows, no admin rights needed)

1. Install a C compiler (MinGW-w64):

       winget install --id BrechtSanders.WinLibs.POSIX.UCRT --source winget --scope user

2. Download PyInstaller's source, the same version as in `.venv`:

       .venv\Scripts\python.exe -m pip download pyinstaller==6.22.2 --no-binary :all: --no-deps -d <temp folder>

3. Extract it, delete the prebuilt `PyInstaller\bootloader\Windows-64bit-intel\*.exe`,
   put the compiler's `mingw64\bin` first in `PATH`, and from its `bootloader` folder run:

       ..\..\path\to\.venv\Scripts\python.exe ./waf all --gcc --target-arch=64bit

4. Install that source tree into `.venv`:

       .venv\Scripts\python.exe -m pip install --no-deps --force-reinstall <extracted folder>

5. Check that `runw.exe` only imports Windows system DLLs (no MinGW DLLs):

       objdump -p .venv\Lib\site-packages\PyInstaller\bootloader\Windows-64bit-intel\runw.exe | findstr "DLL Name"

When PyInstaller is upgraded, add the new wheel's `runw.exe` hash to `_STOCK_RUNW` in
`PunkBackup.spec` and repeat the steps.

# Building the packaged Windows release

PokéRando's packaged Windows release is designed to run without requiring the
end user to install Python, devkitPro, MSYS2, GNU Make, GCC, libpng, or the ARM
compiler.

The release layout is:

```text
PokemonEmeraldRandomizer/
    Randomizer.exe
    game/
    internal/
        baseline/
        tools/
            windows/
                msys64/
                toolchain/
    output/
```

The application already understands this layout through
`randomizer/runtime_paths.py`. Frozen builds deliberately refuse to fall back
to tools installed on the user's computer.

## 1. Prepare the portable build environment

The large Windows tool bundle is intentionally not stored in normal Git
history. It must exist locally at:

```text
randomizer/tools/windows/
    msys64/
    toolchain/
```

The MSYS2 tree must contain the host-side tools needed by the
pokeemerald-expansion build, including GNU Make, GCC/G++, pkg-config, Git,
libpng and zlib development headers/libraries.

The separate `toolchain` directory must contain the ARM bare-metal toolchain,
including `bin/arm-none-eabi-gcc.exe`.

Validate the bundle before packaging:

```powershell
python .\randomizer\windows_toolchain_check.py
```

Do not continue until it reports `PASS`.

## 2. Install the packaging dependency

The release builder uses PyInstaller to freeze the Python GUI:

```powershell
python -m pip install pyinstaller
```

PyInstaller must be run on Windows to produce the Windows executable.

## 3. Build the release

From the repository root:

```powershell
python .\build_windows_release.py
```

The completed folder is written to:

```text
dist/PokemonEmeraldRandomizer/
```

The packager:

1. validates the portable Windows tool bundle;
2. copies the game/source tree without Git metadata, generated ROMs, build
   output, or the development copy of the Windows tools;
3. copies baseline data to `internal/baseline`;
4. copies the portable tools to `internal/tools/windows`;
5. creates `output/`;
6. freezes `randomizer/gui.py` as `Randomizer.exe`.

## 4. Release test

Do not treat a successful packaging run as sufficient validation. Copy the
whole `PokemonEmeraldRandomizer` directory to a clean Windows environment
where Python, devkitPro and MSYS2 are not installed or are not on `PATH`.

Run `Randomizer.exe`, randomise a ROM, and confirm the log reports:

```text
Frozen application: True
Build backend: bundled Windows
```

The test is complete only when the packaged application successfully produces
the final randomized `.gba` in its `output` directory.

## Toolchain provenance

Keep a record of the exact MSYS2 packages and ARM toolchain version used to
create a release. The portable binary bundle should not be silently replaced
with arbitrary files from a developer machine. A future improvement should
make acquisition of this bundle reproducible in CI and publish it as a
versioned release/CI artifact rather than committing it to normal Git history.

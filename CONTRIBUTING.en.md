# Working with the package

[Русский](CONTRIBUTING.md) | **English**

First introduction with an agent: [START_WITH_AI.en.md](docs/START_WITH_AI.en.md).
Project map and verification order: [AGENTS.en.md](AGENTS.en.md).

Russian is the source language of user documentation; English translations
are adjacent `.en.md` files. The desktop interface remains Russian;
code comments may be English. Dependencies and instructions must remain
portable: do not add personal COM ports, Bluetooth addresses or the
developer's absolute paths. Add Russian material first and translate
it afterwards; see [translation workflow](docs/TRANSLATIONS.en.md).

After client changes, run application and protocol tests. After HDL
changes, run simulation, QSF checks, a full Quartus compile and timing
checks. A successful build does not confirm board programming or
hardware accuracy.

Do not overwrite original measurements, captures or historical manifests.
A new series gets a separate folder with conditions and firmware hash.
Mark erroneous data explicitly rather than replacing it with interpolation.
Before updating manifest.json, preserve the reason for and checks of
the change.

Original materials are licensed under MIT and CERN-OHL-P-2.0;
scope: [NOTICE.en.md](NOTICE.en.md).

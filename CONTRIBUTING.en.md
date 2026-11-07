# Working with this package

[Русский](CONTRIBUTING.md) · **English**

For a first session with an agent, see [START_WITH_AI.md](docs/START_WITH_AI.en.md). The project map and verification workflow are in [AGENTS.md](AGENTS.en.md).

Documentation is published in Russian first and translated into English afterwards. See [the translation workflow](docs/TRANSLATION.en.md). The desktop application currently has a Russian interface; source comments may be English. Dependencies and instructions must remain portable: do not add personal COM ports, Bluetooth addresses or developer-specific absolute paths.

After client changes, run application and protocol tests. After HDL changes, run simulations, check QSF, perform a full Quartus compile and review timing. A successful build does not confirm programming of a board or hardware accuracy.

Do not overwrite original measurements, screenshots or historical manifests. Each new series gets its own directory with conditions and firmware hash. Mark erroneous data explicitly rather than substituting interpolated values. Before updating manifest.json, retain information about the reason for the change and the checks performed.

Original materials are licensed under MIT and CERN-OHL-P-2.0; scope is described in [NOTICE.md](NOTICE.en.md).

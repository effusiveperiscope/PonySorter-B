# What is this?
Utility for sorting PPP data. If you don't know what that means, you probably
don't need it.

# Usage
* If you are installing in python/conda, `pip install -r requirements.txt`. On
  Windows you can download an appropriate release.
* In `config.yaml`, modify `master_file_1` to point to master file 1, or the
  directory enclosing `Sliced dialogue`. Modify `master_file_2` to point to
  master file 2. `PonySorter_B` relies on the directory structure following that
  of the master files.

* Add episode tracks (i.e. `s01e01_demu0.flac`), processed and unprocessed, in
  `in_audio`. The current search for classifying tracks relies on alternative
  versions of tracks being located inside the same folder. Currently tracks of interest are
  hosted
  [here](https://drive.google.com/drive/folders/1CY2c7oW3KRPsyta-EyTlpvo8zeccQjCy).

![](https://raw.githubusercontent.com/effusiveperiscope/PonySorter-B/main/docs/1.png)

* Load an episode via the file menu (Ctrl+1).
* If desired, you can filter audios by labeled noise level using the filter dialog (Ctrl+F).
* Preview different processed audios using the buttons or keys `1-4`.
* Select the best sounding audio using the radio buttons or keys `q-r`.
* If necessary, re-label the noise level using the radio buttons or keys `a-d`.
* The sorting state can be saved to a project file using `File>Save` (Ctrl+S).
    * The first save gives you the option to set the save as a default project,
      to be loaded on startup.
    * You can manually change the default project in `config.yaml`.
* `File>Export data for current episode` will export into the `export` directory
  audacity label files AND automatically re-clipped audio, matching the file
  structure of the master file.
* Multiple episodes can be modified in one project. `File>Export data for all`
  will export audacity label files and re-clipped audio for all episodes. Keep
  in mind this could take a long time with a larger amount of episodes.
* I recommend making backups of project files since this software is not very
  well tested.

# Denoising process
* [Code used for index json generation from label files (see "generate_fim_episodes_labels_index")](https://github.com/effusiveperiscope/PPPDataset/blob/main/ppp.py)
* [Code used to denoise](https://github.com/effusiveperiscope/PPPDataset/blob/main/episodes_demucs.ipynb)

# Building (for Windows distribution)
* `pyinstaller ponysorter_b.spec`

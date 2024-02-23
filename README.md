# Usage
* In `config.yaml`, modify `master_file_1` to point to master file 1, or the directory enclosing `Sliced dialogue`. `PonySorter_B` relies on the directory structure following that of the master file. master_file_2 is currently unused and can be left empty.
* Add audios in `in_audio`. They can be located anywhere in a subdirectory of `in_audio` as long as they follow the signature `s**e**_**optional tag**.flac`, e.g. `s01e01.flac` or `s01e01_demu0.flac`. Text after the underscore is interpreted as a label for classification purposes.
* Custom audios can also be used: `signature_tag.flac`.
* `pip install -r requirements.txt`
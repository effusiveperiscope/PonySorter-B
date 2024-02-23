from omegaconf import OmegaConf
import os

CONFIG_PATH = 'config.yaml'
def load_config():
    if os.path.exists(CONFIG_PATH):
        config = OmegaConf.load(CONFIG_PATH)
    else:
        config = OmegaConf.create({
            'master_file_1' : 'D:/MLP_Samples/AIData/Master file',
            'master_file_2' : '', # Not needed for dialogue processing but reserved
            'in_audio_dir': 'in_audio', # Dir in which input audio tracks are placed
            'default_project': '',
            'load_project': '', # Load project on startup 
            'exp_dir': 'export',
            'index_file': 'episodes_labels_index.json', # JSON file with all labels
            'hash_file': 'hashes.json', # JSON file with 'ground truth' hashes
            'audio': {
                'sr': 48000,
                'sample_width_bytes': 4,
                'file_format': 'flac'
            },
            'tag_display_map': {
                'demu0': 'SFX Demucs 1',
                'demu1': 'SFX Demucs 2',
                'master_ver': 'Master File Ver',
                'orig': 'Original'
            },
            'episode_pattern': r's(\d{2})e(\d{2})' # regex for matching ep names
        })
    return config

def save_config(config):
    with open(CONFIG_PATH,'w') as fp:
        OmegaConf.save(config=config, f=fp)
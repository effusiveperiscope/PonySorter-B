AUDIO_DIR = 'sup_audio'
import os
import pydub
import pygame
from config import load_config
from pathlib import Path
from pydub import AudioSegment

audio_dict = {}
assert os.path.exists(AUDIO_DIR)
for f in os.listdir(AUDIO_DIR):
    if f.endswith('.wav'):
        stem = Path(f).stem
        audio_dict[stem] = f

cfg = load_config()
def sl_hook(s):
    if not cfg.get('screenless_mode', False):
        return
    if not s in audio_dict:
        return
    _sound = pygame.mixer.Sound(os.path.join(AUDIO_DIR,audio_dict[s]))
    _sound.play()
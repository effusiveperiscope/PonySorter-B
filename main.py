from config import load_config, save_config
from gui import gui_main

if __name__ == '__main__':
    conf = load_config()
    gui_main(conf)
    save_config(conf)
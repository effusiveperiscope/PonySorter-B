import os
import re
import json
import shutil
import copy
from hashes import Hasher
from pydub import AudioSegment
from utils import sanitize_file_name, mergedicts, label_reparse, path_reparse
from pathlib import Path
from log import logger
from config import save_config
from collections import OrderedDict

def gather_available_audio(conf):
    index = {}
    for (root,_,files) in os.walk(conf['in_audio_dir']):
        for f in files:
            if not f.endswith(conf['audio']['file_format']):
                continue
            match_s = re.search(conf['episode_pattern'], f)
            tag = f.removesuffix('.flac').split('_')[-1]
            if match_s:
                sig = f's{match_s.group(1)}e{match_s.group(2)}'
                if not sig in index:
                    index[sig] = {
                        'schema': 'episode'
                    }
                if not '_' in f:
                    index[sig]['orig'] = os.path.join(root,f)
                else:
                    if tag == 'master_ver' or tag == 'orig':
                        logger.warn(f'Reserved tag {tag} found on '
                            f'{os.path.join(root,f)}, skipping this file')
                        continue
                    index[sig][tag] = os.path.join(root,f)
            else:
                assert len(f.split('_')) <= 2
                sig = f.removesuffix('.flac').split('_')[0]
                index[sig] = {
                    'schema': 'custom'
                }
    return index

def subsegment(source, line):
    return source[int(float(line['ts'])*1000):int(float(line['te'])*1000)]

def sig_to_labels_key(sig):
    return f's{int(sig[1:3])}e{int(sig[4:6])}'

class PonySorter_B:
    def __init__(self, conf):
        self.conf = conf
        self.hasher = Hasher(conf)
        self.audios_index = gather_available_audio(conf)
        self.loaded_sig = ''

        if not len(self.audios_index):
            logger.warn(f'No audios found in {conf["in_audio_dir"]}')
        if not os.path.exists(conf['index_file']):
            logger.warn(f'Index file {conf["index_file"]} not found')

        with open(conf['index_file'], encoding='utf-8') as f:
            self.labels_index = json.load(f)

        self.modified_index = {}
        self.dirty_flag = False

    def get_sigs(self):
        return self.audios_index.keys()

    def get_season_ep_sigs(self):
        return [k for k,v in self.audios_index.items() if v[
            'schema'] == 'episode']

    def key_transform(self, sig):
        if self.audios_index[sig]['schema'] == 'episode':
            return sig_to_labels_key(sig)
        else:
            return sig

    def get_lines_for_sig(self, sig, from_idx=None):
        if from_idx is None:
            from_idx = self.labels_index
        key = self.key_transform(sig)
        if not key in from_idx:
            logger.warn(f"Signature {sig} from audio but no corresponding label")
            return None
        return from_idx[key]['lines']

    def load_sig(self, sig, load_callback=None):
        if sig == self.loaded_sig: # no scenario where need to load twice
            return len(self.lines)
        self.loaded_sig = sig
        self.sources = {}
        self.lines = self.get_lines_for_sig(sig)
        for l in self.lines:
            if not 'selected_tag' in l:
                l['selected_tag'] = 'master_ver'
            if not 'original_noise' in l:
                l['original_noise'] = l['parse']['noise']
        len_items = len(self.audios_index[sig])
        for i,t in enumerate(self.audios_index[sig].items()):
            tag,path = t
            if tag == 'schema':
                continue

            # File integrity checking
            chk = self.hasher.check_hash(path)
            if chk == False:
                logger.warn(f"Hash mismatch on {path}")
            elif chk == None:
                logger.info(f"Note - no stored hash for {path}")

            self.sources[tag] = AudioSegment.from_file(path)
            if load_callback is not None:
                load_callback(int((i)/(len_items-1)*100))
        logger.info(f'Loaded {sig}')
        return len(self.lines)

    def load_line(self, i):
        assert hasattr(self,'lines')
        assert i < len(self.lines)
        line = self.lines[i]
        master_file_path = self.lines[i]['orig_file']
        master_file_path = master_file_path.replace(
            'MASTER_FILE_1', self.conf['master_file_1'])
        master_file_path = master_file_path.replace(
            'MASTER_FILE_2', self.conf['master_file_2'])
        preview_segments = OrderedDict()
        preview_segments['master_ver'] = AudioSegment.from_file(master_file_path)
        for tag,source in self.sources.items():
            preview_segments[tag] = subsegment(source, line)
        if 'orig' in preview_segments:
            # I think Original should be last because it's the least common
            preview_segments.move_to_end('orig') 
        return self.sources, self.lines[i], preview_segments

    def edit_line(self, i, select_tag, add_data):
        assert i < len(self.lines)
        if select_tag is not None:
            self.lines[i]['selected_tag'] = select_tag
        if add_data is not None:
            self.lines[i] = dict(mergedicts(self.lines[i], add_data))
        if not self.loaded_sig in self.modified_index:
            self.modified_index[self.loaded_sig] = {}
        self.modified_index[self.loaded_sig][i] = self.lines[i]
        self.dirty_flag = True
        return self.lines[i]

    def save_progress(self, save_name, add_data):
        save_config(self.conf)
        save_dict = {
            'add_data': add_data,
            'modified_index': self.modified_index,
            'loaded_sig': self.loaded_sig
        }
        with open(save_name, 'w') as f:
            json.dump(save_dict, f)
        self.dirty_flag = False

    def load_progress(self, project_name):
        with open(project_name, 'r') as f:
            save_dict = json.load(f)
        self.modified_index = save_dict.get('modified_index', {})

        for sig,lines in self.modified_index.items():
            key = self.key_transform(sig)
            for idx,line in lines.items():
                self.labels_index[key]['lines'][int(idx)] = line

        return save_dict.get('add_data',{}), save_dict

    # Re-export audio in the same structure as the master file
    def export_audio(self, exp_dir, load_cb, sig_to_proc=[]):
        os.makedirs(exp_dir, exist_ok=True)
        sig_ct = len(self.modified_index.items())

        if not len(sig_to_proc):
            sig_to_proc = list(self.modified_index.keys())

        old_loaded_sig = self.loaded_sig
        for i, sig in enumerate(sig_to_proc):
            logger.info(f"Processing {sig}")
            self.load_sig(sig, load_cb)
            line_ct = len(self.lines)

            if len(self.lines):
                expected_save_path = self.lines[0]['orig_file'].replace(
                    '\\','/').replace('MASTER_FILE_1', exp_dir).replace(
                    'MASTER_FILE_2', exp_dir)
                expected_parent = Path(expected_save_path).parent
                # Reset sig tree if parent exists
                if os.path.exists(expected_parent):
                    shutil.rmtree(expected_parent)

            for i,line in enumerate(self.lines):
                load_cb(int(i*100/line_ct))
                orig_file = line['orig_file'].replace(
                    'MASTER_FILE_1', self.conf['master_file_1']).replace(
                    'MASTER_FILE_2', self.conf['master_file_2']) 
                orig_file_transcript = orig_file.removesuffix(
                    '..flac').removesuffix('.flac') + '.txt'
                assert os.path.exists(orig_file_transcript), orig_file_transcript

                save_path = path_reparse(line['orig_file'], line['parse'])
                save_path = save_path.replace('\\','/')
                save_path = save_path.replace('MASTER_FILE_1', exp_dir)
                save_path = save_path.replace('MASTER_FILE_2', exp_dir)
                save_path_parent = Path(save_path).parent
                os.makedirs(save_path_parent, exist_ok=True)

                # If master is used, just copy existing
                if line['selected_tag'] == 'master_ver':
                    shutil.copy(orig_file, save_path)
                else:
                    segment_to_save = subsegment(
                        self.sources[line['selected_tag']], line)
                    segment_to_save.export(save_path, format='flac')

                save_path_transcript = save_path.removesuffix('.flac') + '.txt'
                shutil.copy(orig_file_transcript, save_path_transcript)
        self.load_sig(old_loaded_sig)

    def export_audacity_labels(self, exp_dir, load_cb, sig_to_proc=[]):
        os.makedirs(exp_dir, exist_ok=True)
        new_index = copy.deepcopy(self.labels_index)

        for i, sig in enumerate(self.modified_index.keys()):
            lines = self.get_lines_for_sig(sig, new_index)

            if len(sig_to_proc):
                do_audacity_write = sig in sig_to_proc
            else:
                do_audacity_write = True

            tag_file_handles = {}
            if do_audacity_write:
                base_file_handle = open(os.path.join(exp_dir, sig+'.txt'),'w')

            for l in lines:
                if not 'selected_tag' in l:
                    l['selected_tag'] = 'master_ver'
                if not 'original_noise' in l:
                    l['original_noise'] = l['parse']['noise']

            for j,line in enumerate(lines):
                tag = line['selected_tag']
                label_file = os.path.join(exp_dir, sig+'_'+tag+'.txt')
                if do_audacity_write:
                    if not tag in tag_file_handles:
                        tag_file_handles[tag] = open(label_file, 'w')
                new_label = label_reparse(line['label'], line['parse'])
                key = self.key_transform(sig)
                new_index[key]['lines'][j].pop('original_noise')
                new_index[key]['lines'][j].pop('selected_tag')
                new_index[key]['lines'][j]['label'] = new_label
                new_index[key]['lines'][j]['orig_file'] = path_reparse(
                    line['orig_file'], line['parse'])
                if do_audacity_write:
                    tag_file_handles[tag].write(
                        str(line['ts'])+'\t'+str(line['te'])+'\t'+
                        new_label+'\n')
                    base_file_handle.write(
                        str(line['ts'])+'\t'+str(line['te'])+'\t'+
                        new_label+'\n')
            for f in tag_file_handles.values():
                f.close()

            if do_audacity_write:
                base_file_handle.close()
        # We have to overwrite Label and Orig_File
        with open(os.path.join(
            exp_dir, 'episodes_labels_index_updated.json'), 'w') as f:
            json.dump(new_index, f)
        load_cb(100)
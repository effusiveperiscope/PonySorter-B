import os
import re
import json
import shutil
import copy
from hashes import Hasher
from pydub import AudioSegment
from utils import (
    sanitize_file_name, mergedicts, label_reparse, path_reparse, longpath,
    transcript_transform_path, sigcat)
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

# Initialize line with default values
def prep_line(l):
    if not 'selected_tag' in l:
        l['selected_tag'] = 'master_ver'
    if not 'original_noise' in l:
        l['original_noise'] = l['parse']['noise']
    if not 'original_char' in l:
        l['original_char'] = l['parse']['char']

# TODO: Editing the character
# XXX: Editing the transcript must also edit the resulting transcript file
# It also means that label indexes based on the new transcript

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
        else:
            with open(conf['index_file'], encoding='utf-8') as f:
                self.labels_index = json.load(f)
                self.orig_labels_index = copy.deepcopy(self.labels_index)

        self.modified_index = {}
        self.dirty_flag = False

    def is_loaded(self):
        return hasattr(self,'lines')

    def get_sigs(self):
        return self.audios_index.keys()

    def get_sigs_ordered_by_episode(self):
        return sorted(self.audios_index.keys(), key=lambda s: sigcat(s))

    def get_season_ep_sigs(self):
        return [k for k,v in self.audios_index.items() if v[
            'schema'] == 'episode']

    def key_transform(self, sig):
        if sig not in self.audios_index:
            return sig
        if self.audios_index[sig]['schema'] == 'episode': # keyerror 's01e01
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
        if not hasattr(self, 'labels_index'):
            logger.error(f'Cannot load if label index not available')
            return 0
        self.loaded_sig = sig
        self.sources = {}
        self.lines = self.get_lines_for_sig(sig)
        for l in self.lines:
            prep_line(l)
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

            self.sources[tag] = AudioSegment.from_file(
                longpath(path))
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
        preview_segments['master_ver'] = AudioSegment.from_file(
            longpath(master_file_path))
        for tag,source in self.sources.items():
            preview_segments[tag] = subsegment(source, line)
        if 'orig' in preview_segments:
            # I think Original should be last because it's the least common
            preview_segments.move_to_end('orig') 
        return self.sources, self.lines[i], preview_segments

    def edit_line(self, i, select_tag, add_data, sig=None, verbose=False):
        assert i < len(self.lines)
        if sig is None:
            sig = self.loaded_sig
        lines = self.get_lines_for_sig(sig)
        if select_tag is not None:
            if verbose and lines[i]['selected_tag'] != select_tag:
                logger.info(f"Change {i}: {lines[i]['selected_tag']} -> {select_tag}")
            lines[i]['selected_tag'] = select_tag
        if add_data is not None:
            lines[i] = dict(mergedicts(lines[i], add_data))
        if not sig in self.modified_index:
            self.modified_index[sig] = {}
        # Standardize index as str to avoid weird problems w/ json
        self.modified_index[sig][str(i)] = lines[i]
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

        if not hasattr(self, 'labels_index'):
            logger.error(f'Cannot load a project if label index not available')
            return None, None

        for sig,lines in self.modified_index.items():
            key = self.key_transform(sig)
            if key not in self.labels_index:
                logger.error(f"Key {key} not in labels index")
                return None, None

        for sig,lines in self.modified_index.items():
            key = self.key_transform(sig)
            for idx,line in lines.items():
                self.labels_index[key]['lines'][int(idx)] = line

        return save_dict.get('add_data',{}), save_dict

    # Re-export audio in the same structure as the master file
    def export_audio(self, exp_dir, load_cb, sig_to_proc=[]):
        if not self.is_loaded():
            logger.warn("Nothing to export")
            return
        os.makedirs(exp_dir, exist_ok=True)
        sig_ct = len(self.modified_index.items())

        if not len(sig_to_proc):
            sig_to_proc = list(self.modified_index.keys())
            print(sig_to_proc)

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
                    try:
                        shutil.rmtree(expected_parent)
                    except PermissionError as e:
                        logger.error(e)
                        self.load_sig(old_loaded_sig)
                        raise e

            for i,line in enumerate(self.lines):
                load_cb(int(i*100/line_ct))
                orig_file = line['orig_file'].replace(
                    'MASTER_FILE_1', self.conf['master_file_1']).replace(
                    'MASTER_FILE_2', self.conf['master_file_2']) 
                orig_file_transcript = transcript_transform_path(orig_file)
                assert os.path.exists(longpath(orig_file_transcript)), orig_file_transcript

                save_path = path_reparse(line['orig_file'], line['parse'])
                save_path = save_path.replace('\\','/')
                save_path = save_path.replace('MASTER_FILE_1', exp_dir)
                save_path = save_path.replace('MASTER_FILE_2', exp_dir)
                save_path_parent = Path(save_path).parent
                os.makedirs(save_path_parent, exist_ok=True)

                # If master is used, just copy existing
                if line['selected_tag'] == 'master_ver':
                    shutil.copy(longpath(orig_file), longpath(save_path))
                else:
                    segment_to_save = subsegment(
                        self.sources[line['selected_tag']], line)
                    segment_to_save.export(longpath(save_path), format='flac')

                save_path_transcript = transcript_transform_path(save_path)
                shutil.copy(longpath(orig_file_transcript), 
                    longpath(save_path_transcript))
        self.load_sig(old_loaded_sig)

    def export_audacity_labels(self, exp_dir, load_cb, sig_to_proc=[]):
        if not self.is_loaded():
            logger.warn("Nothing to export")
            return
        os.makedirs(exp_dir, exist_ok=True)
        new_index = copy.deepcopy(self.labels_index)

        # Replay changes
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
                prep_line(l)

            for j,line in enumerate(lines):
                tag = line['selected_tag']
                label_file = os.path.join(exp_dir, sig+'_'+tag+'.txt')
                if do_audacity_write:
                    if not tag in tag_file_handles:
                        tag_file_handles[tag] = open(label_file, 'w')
                new_label = label_reparse(line['label'], line['parse'])
                key = self.key_transform(sig)
                new_index[key]['lines'][j].pop('original_noise')
                new_index[key]['lines'][j].pop('original_char')
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

    def import_from_label_files(self, files):
        for f in files:
            fn = Path(f).name
            sp = fn.removesuffix('.txt').split('_')
            if len(sp) == 1:
                continue # Then this is just the master
            sig = sp[0]
            tag = sp[1]
            if tag == 'master':
                tag = 'master_ver'

            logger.info(f'Importing {sig}, tag {tag} from {fn}')

            lines = self.get_lines_for_sig(sig)
            lines_index_map = {
                str(v['ts'])+str(v['te']):i for i,v in enumerate(lines)}

            with open(f, encoding='utf-8') as fp:
                entries = fp.read()

            if not sig in self.modified_index:
                self.modified_index[sig] = {}

            entries = entries.split('\n')
            for e in entries:
                if not len(e.strip()):
                    continue
                sp = e.split('\t')
                if not len(sp):
                    continue
                # Lines can be uniquely identified by episode + start timestamp + end timestamp
                ts = sp[0].strip()
                te = sp[1].strip()
                label = sp[2].strip()
                key = str(ts)+str(te)
                if not key in lines_index_map:
                    logging.warn(f"Could not find entry {e}")
                    continue
                label_sp = label.split('_')
                char = label_sp[3]
                noise = label_sp[5]
                idx = lines_index_map[key]
                self.edit_line(idx, tag, 
                    {'parse': {'noise':noise, 'char':char}}, sig=sig, verbose=True)
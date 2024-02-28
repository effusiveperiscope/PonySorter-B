import re
import os
from pathlib import Path

def sanitize_file_name(file_name):
    # Remove characters that are not allowed in file names
    sanitized_name = re.sub(r'[^\w\-_.() ]', '', file_name)
    # Replace spaces with underscores
    sanitized_name = sanitized_name.replace(' ', '_')
    return sanitized_name

shifts = '''aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ1!2@3#4$5%6^7&8*9(0)`~,<.>/?;:'"[{]}\|-_=+'''
shift_map = {}
for i in range(0, len(shifts), 2):
    shift_map[shifts[i]] = shifts[i+1]

def key_shift(key):
    key = str(key)
    return shift_map[key]

def mergedicts(dict1, dict2):
    for k in set(dict1.keys()).union(dict2.keys()):
        if k in dict1 and k in dict2:
            if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
                yield (k, dict(mergedicts(dict1[k], dict2[k])))
            else:
                # If one of the values is not a dict, you can't continue merging it.
                # Value from second dict overrides one in first and we move on.
                yield (k, dict2[k])
                # Alternatively, replace this with exception raiser to alert you of value conflicts
        elif k in dict1:
            yield (k, dict1[k])
        else:
            yield (k, dict2[k])

def label_reparse(label, parse_src):
    sp = label.split('_')
    sp[5] = parse_src['noise']
    return '_'.join(sp)

def path_reparse(orig_file, parse_src):
    parent = Path(orig_file).parent
    name = Path(orig_file).name
    out_path = parent / label_reparse(name, parse_src)
    return str(out_path)

qwertymap0 = '1234567890'
qwertymap1 = 'qwertyuiop'
qwertymap2 = 'asdfghjkl;'

def longpath(path):
    import platform
    path = os.path.abspath(path)
    if 'Windows' in platform.system() and not path.startswith('\\\\?\\'):
        path = u'\\\\?\\'+path.replace('/','\\')
        return path
    else:
        return path

def transcript_transform_path(path):
    return path.removesuffix('.flac').rstrip().rstrip('.') + '.txt'

def sigcat(sig):
    nums = re.findall(r'\d+',sig)
    return int(''.join(nums))

from tqdm import tqdm
def test_transcript_transform(sliced_dialogue = "D:/MLP_Samples/AIData/Master file/Sliced Dialogue"):
    print("Checking...")
    for (root, _, files) in os.walk(sliced_dialogue):
        #print(f'Checking root {root}')
        for f in files:
            if not f.endswith('.flac'):
                continue
            transcript_path = transcript_transform_path(os.path.join(root, f))
            if not os.path.exists(longpath(transcript_path)):
                print(f'Anomalous path {transcript_path}')
            #assert os.path.exists(longpath(transcript_path)), transcript_path

def test_unique_identifier(sliced_dialogue = "D:/MLP_Samples/AIData/Master file/Sliced Dialogue"):
    print("Checking...")
    for (root, _, files) in os.walk(sliced_dialogue):
        #print(f'Checking root {root}')
        seen = set()
        for f in files:
            if not f.endswith('.flac'):
                continue
            fn = Path(f).name
            sp = fn.split('_')
            ident = '_'.join(sp[0:3])
            if ident in seen:
                print(f'Duplicate ident {fn} in {root}')
            seen.add(ident)

if __name__ == '__main__':
    test_transcript_transform()
    #test_unique_identifier(r"D:\MEGASyncDownloads\Master file 2\Songs")
import re
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
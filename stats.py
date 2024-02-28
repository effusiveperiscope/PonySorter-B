from PyQt5.QtWidgets import (QWidget, QApplication, QMainWindow, QVBoxLayout,
    QHBoxLayout, QFrame, QPushButton, QPlainTextEdit, QGroupBox, QRadioButton,
    QSizePolicy, QGridLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QComboBox, QDialog, QProgressBar, QFileDialog, QMessageBox,
    QAbstractItemView)
from merge import FileButton
import os
import json
import copy
from pathlib import Path
from functools import partial, reduce
from log import logger
from utils import sigcat
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.cm as cm
import numpy as np

def compare_sigs(orig_sig, new_sig, modified_sig):
    orig_lines = orig_sig['lines']

    stats = {}
    stats['convs'] = {}
    stats['convs']['noisy_to_clean'] = 0
    stats['convs']['noisy_to_noisy'] = 0
    stats['convs']['very_noisy_to_clean'] = 0
    stats['convs']['very_noisy_to_noisy'] = 0
    stats['convs']['demu0'] = 0
    stats['convs']['demu1'] = 0
    stats['totals'] = {}
    stats['totals']['total'] = len(orig_lines)
    stats['totals']['modified'] = 0
    stats['totals']['clean_pre'] = 0
    stats['totals']['noisy_pre'] = 0
    stats['totals']['very_noisy_pre'] = 0
    stats['totals']['clean_post'] = 0
    stats['totals']['noisy_post'] = 0
    stats['totals']['very_noisy_post'] = 0

    stats['totals']['demu0_preferred'] = 0
    stats['totals']['demu1_preferred'] = 0
    stats['totals']['master_preferred'] = 0
    stats['totals']['none_preferred'] = 0

    for line_idx, orig_line in enumerate(orig_lines):
        new_line = new_sig['lines'][line_idx]
        line_idx = str(line_idx)
        modified_line = modified_sig.get(line_idx, None)

        if new_line['parse']['noise'] == '':
            stats['totals']['clean_post'] += 1
        elif new_line['parse']['noise'] == 'Noisy':
            stats['totals']['noisy_post'] += 1
        elif new_line['parse']['noise'] == 'Very Noisy':
            stats['totals']['very_noisy_post'] += 1

        if orig_line['parse']['noise'] == '':
            stats['totals']['clean_pre'] += 1
        elif orig_line['parse']['noise'] == 'Noisy':
            stats['totals']['noisy_pre'] += 1
            if modified_line is None: 
                stats['totals']['master_preferred'] += 1
                continue
            if modified_line['parse']['noise'] == '':
                stats['convs']['noisy_to_clean'] += 1
            if modified_line['parse']['noise'] == 'Noisy':
                stats['convs']['noisy_to_noisy'] += 1
            # A line is only considered modified if demu0 or demu1 is selected.
            # Of all noisy/very noisy lines,
            # for how many were either of the demucs models preferred?
            if modified_line['selected_tag'] == 'demu0':
                stats['totals']['demu0_preferred'] += 1
                stats['totals']['modified'] += 1
            elif modified_line['selected_tag'] == 'demu1':
                stats['totals']['demu1_preferred'] += 1
                stats['totals']['modified'] += 1
        elif orig_line['parse']['noise'] == 'Very Noisy':
            stats['totals']['very_noisy_pre'] += 1
            if modified_line is None: 
                stats['totals']['none_preferred'] += 1
                continue
            if modified_line['parse']['noise'] == '':
                stats['convs']['very_noisy_to_clean'] += 1
            if modified_line['parse']['noise'] == 'Noisy':
                stats['convs']['very_noisy_to_noisy'] += 1
            if modified_line['selected_tag'] == 'demu0':
                stats['totals']['demu0_preferred'] += 1
                stats['totals']['modified'] += 1
            elif modified_line['selected_tag'] == 'demu1':
                stats['totals']['demu1_preferred'] += 1
                stats['totals']['modified'] += 1

        if modified_line is None: 
            continue
        # What percentage of modified were demucs0 and demucs1?
        if modified_line['selected_tag'] == 'demu0':
            stats['convs']['demu0'] += 1
        elif modified_line['selected_tag'] == 'demu1':
            stats['convs']['demu1'] += 1

    return stats

def sum_dicts(a,b):
    return {t1[0]: t1[1] + t2[1] for t1,t2 in zip(a.items(), b.items())}

def sum_stats(a,b):
    return {'convs': sum_dicts(a['convs'],b['convs']),
     'totals': sum_dicts(a['totals'], b['totals'])}

def div_or_zero(a,b):
    if b == 0:
        return 0
    return a / b

def props_stats(a):
    try:
        props = { k: v / a['totals']['total'] 
            for k,v in a['totals'].items()} # proportion of total lines
        props.update({ k: v / a['totals']['modified'] 
            for k,v in a['convs'].items()}) # proportion of modified
    except ZeroDivisionError as e:
        logger.warn(e)
        props = { k: div_or_zero(v, a['totals']['total'])
            for k,v in a['totals'].items()} # proportion of total lines
        props.update({ k: div_or_zero(v, a['totals']['modified'])
            for k,v in a['convs'].items()}) # proportion of modified
    return props

def stats_displayof(sig, s):
    props = props_stats(s)

    # Episode comparison:
    # Which episodes had the highest/lowest percentage of modified lines?
    # This is just a flat proportion and can be done in an aggregate bar chart

    # What were the proportions of clean/noisy/very noisy pre and post?
    # This is one of the rare cases where we it is feasible to do a grouped stacked bar chart
    # Stacked bar chart
    labels = ['Pre', 'Post']
    clean_props = np.array([props['clean_pre'], props['clean_post']])
    noisy_props = np.array([props['noisy_pre'], props['noisy_post']])
    very_noisy_props = np.array([props['very_noisy_pre'], props['very_noisy_post']])

    fig1 = Figure(figsize=(4,5), dpi=100)
    canv1 = FigureCanvas(fig1)
    ax1 = fig1.add_subplot(111)
    ax1.bar(labels, clean_props, label='Clean')
    ax1.bar(labels, noisy_props, bottom=clean_props, label='Noisy')
    ax1.bar(labels, very_noisy_props, bottom=clean_props+noisy_props, label='Very noisy')

    #names1 = ( 'Pre', 'Post' )
    #props1 = {
    #    'Clean' : np.array([props['clean_pre'], props['clean_post']]),
    #    'Noisy' : np.array([props['noisy_pre'], props['noisy_post']]),
    #    'Very noisy' : np.array([props['very_noisy_pre'], props['very_noisy_post']])}
    #bottom = np.zeros(len(props1))
    #for k,v in props1.items():
    #    p = ax1.bar(names1, v, 0.5, label=k, bottom=bottom)
    #    bottom += v

    # At what proportion of noisy/very noisy items
    # were we able to upgrade to a lower noise level?
    # This is just two proportions, or two stacked items, and can be done either in a grouped chart
    # or in a grouped stacked bar chart

    # Given a noisy/very noisy audio, at what proportion did we prefer demucs0/demucs1?
    # This is just a flat proportion and can be done in an aggregate bar chart

    # So all of these can be done in the aggregate and there is not a real need for per-episode
    # bar charts?

    return canv1

def stats_dialog(cur_core, exp_dir): 
    dialog = QDialog()
    dialog.setWindowTitle('Calculate statistics for current project')
    dialog_lay = QVBoxLayout(dialog)

    if not hasattr(cur_core, 'lines') or not len(cur_core.modified_index):
        logger.info('No data available for statistics')
        return
    orig_index = cur_core.orig_labels_index
    new_index = cur_core.labels_index

    stats_dict = {}

    # Only calculate stats for signatures in the modified index.
    for sig in cur_core.modified_index.keys():
        key = cur_core.key_transform(sig)
        if key not in orig_index:
            logger.warn(f"Project signature {sig} (key {key}) not present in original index!")
            continue
        stats = compare_sigs(orig_index[key], new_index[key], 
            cur_core.modified_index[sig])
        stats_dict[sig] = stats
    aggregate_dict = reduce(sum_stats, (s for s in stats_dict.values()))

    stats_pairs = [(k,v) for k,v in stats_dict.items()]
    stats_pairs = sorted(stats_pairs, key=lambda x: sigcat(x[0]))
    stats_dict = {x[0]:x[1] for x in stats_pairs}

    props_dict = {k:props_stats(v) for k,v in stats_dict.items()}

    # 1 Which episodes had the highest/lowest percentage of modified lines?
    tu = [(k,v['modified']) for k,v in props_dict.items()]
    #tu = sorted(tu, key=lambda t: t[1])
    labels = [t[0] for t in tu]
    props = [t[1] for t in tu]
    fig1 = Figure(figsize=(16,8), dpi=60)
    canv = FigureCanvas(fig1)
    canv.setMinimumHeight(300)
    ax = fig1.add_subplot(111)
    ax.bar(labels, props, width=0.5)
    ax.grid(axis="y")
    ax.set_title('Proportion of lines which were modified')
    dialog_lay.addWidget(canv)

    # 2 What were the balances of clean/noisy/very noisy pre and post?
    fig2 = Figure(figsize=(16,10), dpi=80)
    canv = FigureCanvas(fig2)
    ax = fig2.add_subplot(111)

    clean_pre = np.array([
        s['totals']['clean_pre'] for s in stats_dict.values()])
    clean_post = np.array([
        s['totals']['clean_post'] for s in stats_dict.values()])
    noisy_pre = np.array([
        s['totals']['noisy_pre'] for s in stats_dict.values()])
    noisy_post = np.array([
        s['totals']['noisy_post'] for s in stats_dict.values()])
    very_noisy_pre = np.array([
        s['totals']['very_noisy_pre'] for s in stats_dict.values()])
    very_noisy_post = np.array([
        s['totals']['very_noisy_post'] for s in stats_dict.values()])
    i = np.arange(len(stats_dict))

    cmap = cm.viridis_r
    ax.bar(i,clean_pre,width=.33,label='clean_pre',color=cmap(0))
    ax.bar(i+.33,clean_post,width=.33,label='clean_post',color=cmap(0.1))
    ax.bar(i,noisy_pre,width=.33,label='noisy_pre',
        bottom=clean_pre,color=cmap(0.33))
    ax.bar(i+.33,noisy_post,width=.33,label='noisy_post',
        bottom=clean_post,color=cmap(0.43))
    ax.bar(i,very_noisy_pre,width=.33,label='very_noisy_pre',
        bottom=clean_pre+noisy_pre,color=cmap(0.66))
    ax.bar(i+.33,very_noisy_post,width=.33,label='very_noisy_pre',
        bottom=clean_post+noisy_post,color=cmap(0.76))
    ax.legend(bbox_to_anchor=(1.1,1.05), ncol=3)
    ax.set_xticks(i, [k for k in stats_dict.keys()])
    ax.grid(axis="y")
    ax.set_title('Noise quality, pre and post', loc='left')
    #fig.savefig('noise_qual.png', dpi=300)
    dialog_lay.addWidget(canv)

    # 3 What proportion of noisy/very noisy items could we upgrade?
    fig3 = Figure(figsize=(16,10), dpi=80)
    canv = FigureCanvas(fig3)
    demu0_preferred = np.array(
        [s['totals']['demu0_preferred'] for s in stats_dict.values()])
    demu1_preferred = np.array(
        [s['totals']['demu1_preferred'] for s in stats_dict.values()])
    remainder = (noisy_pre + very_noisy_pre) - (demu0_preferred + demu1_preferred)
    canv = FigureCanvas(fig3)
    ax = fig3.add_subplot(111)
    prop_upgraded = (demu0_preferred + demu1_preferred) / (noisy_pre + very_noisy_pre)
    bars = ax.bar(i,noisy_pre + very_noisy_pre,width=.5,
        label='noisy or very noisy', edgecolor=cmap(1), linewidth=2, facecolor='none')
    ax.bar(i,demu0_preferred,width=.5,label='demu0 preferred', color=cmap(0.3))
    ax.bar(i,demu1_preferred,width=.5,label='demu1 preferred',
        bottom=demu0_preferred, color=cmap(0.6))
    for bar,prop in zip(bars, prop_upgraded): # proportion readouts
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval+2, f'{prop:.3f}',
            ha='center', va='bottom')
    ax.set_xticks(i, [k for k in stats_dict.keys()])
    ax.grid(axis="y")
    ax.set_title("Modification of noisy lines (prop = of noisy lines modified)",
        loc='left')
    ax.legend(bbox_to_anchor=(1.1,1.05), ncol=3)
    dialog_lay.addWidget(canv)

    # totals(demu0_preferred + demu1_preferred) / (noisy_pre + very_noisy_pre)
    def save_cb():
        DPI = 300
        fig1.savefig(os.path.join(exp_dir,'Proportion modified.png'),dpi=DPI)
        fig2.savefig(os.path.join(exp_dir,'Noise mix pre and post.png'),dpi=DPI)
        fig3.savefig(os.path.join(exp_dir,'Upgrades by model.png'),dpi=DPI)
        logger.info(f'Saved graphs to {exp_dir}')
    save_button = QPushButton('Save graphs to export dir')
    save_button.pressed.connect(save_cb)
    dialog_lay.addWidget(save_button)

    # Which model was preferred?

    #import pdb
    #from PyQt5.QtCore import pyqtRemoveInputHook
    #pyqtRemoveInputHook()
    #pdb.set_trace()

    dialog.exec_()
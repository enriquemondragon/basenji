# Copyright 2017 Calico LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========================================================================

from collections import OrderedDict
import pdb
import sys

import h5py
import numpy as np
import pandas as pd

import basenji.dna_io
from basenji.gene import TSS, GeneSeq

class GeneData:
  def __init__(self, genes_hdf5_file, worker_index=None, workers=None):
    # open HDF5
    self.genes_hdf5_in = h5py.File(genes_hdf5_file)

    # simple stats
    self.num_seqs, self.seq_length, self.seq_depth = self.genes_hdf5_in['seqs_1hot'].shape
    self.pool_width = int(np.array(self.genes_hdf5_in['pool_width']))

    #########################################
    # gene sequences

    self.gene_seqs = []
    for si in range(len(self.genes_hdf5_in['seq_chrom'])):
      gene_seq = GeneSeq(self.genes_hdf5_in['seq_chrom'][si].decode('UTF-8'),
                         self.genes_hdf5_in['seq_start'][si],
                         self.genes_hdf5_in['seq_end'][si])
      self.gene_seqs.append(gene_seq)

    self.seqs_1hot = np.array(self.genes_hdf5_in['seqs_1hot'])

    #########################################
    # TSS information

    self.tss = []

    for tss_i in range(len(self.genes_hdf5_in['tss_id'])):
      # map to gene seq
      seq_i = self.genes_hdf5_in['tss_seq'][tss_i]
      tss_seq = self.gene_seqs[seq_i]

      # read in TSS
      tss = TSS(self.genes_hdf5_in['tss_id'][tss_i].decode('UTF-8'),
                self.genes_hdf5_in['tss_gene'][tss_i].decode('UTF-8'),
                self.genes_hdf5_in['tss_chrom'][tss_i].decode('UTF-8'),
                self.genes_hdf5_in['tss_pos'][tss_i],
                tss_seq)
                # tss_seq,
                # self.genes_hdf5_in['tss_strand'][tss_i].decode('UTF-8'))
      self.tss.append(tss)

      # append to GeneSeq
      tss_seq.tss_list.append(tss)


    #########################################
    # determine genes split across sequences

    gene_seqs = {}
    for seq_i in range(self.num_seqs):
      for tss in self.gene_seqs[seq_i].tss_list:
        gene_seqs.setdefault(tss.gene_id,set()).add(seq_i)

    self.multi_seq_genes = set()
    for gene_id in gene_seqs:
        if len(gene_seqs[gene_id]) > 1:
            self.multi_seq_genes.add(gene_id)


    #########################################
    # target information

    if 'tss_targets' in self.genes_hdf5_in:
      self.tss_targets = self.genes_hdf5_in['tss_targets']
      self.target_labels = [tl.decode('UTF-8') for tl in self.genes_hdf5_in['target_labels']]
      if 'target_ids' in self.genes_hdf5_in:   # TEMP
        self.target_ids = [tl.decode('UTF-8') for tl in self.genes_hdf5_in['target_ids']]
      else:
        self.target_ids = ['']*len(self.target_labels)
      self.num_targets = len(self.target_labels)

    else:
      self.tss_targets = None
      self.target_ids = None
      self.target_labels = None
      self.num_targets = None



  def gene_ids(self):
    """ Return a list of gene identifiers """
    return list(self.gene_tss().keys())


  def gene_tss(self):
    """ Return an OrderedDict mapping gene_id's to TSS indexes. """
    gene_tss = OrderedDict()
    for tss_i in range(len(self.tss)):
      gene_tss.setdefault(self.tss[tss_i].gene_id,[]).append(tss_i)
    return gene_tss


  def tss_ids(self):
    """ Return a list of TSS identifiers """
    return [tss.identifier for tss in self.tss]


  def worker(self, wi, worker_num):
    """ Limit the sequences to one worker's share. """

    worker_mask = np.array(
        [si % worker_num == wi for si in range(self.num_seqs)])

    # filter gene sequences
    self.seqs_1hot = self.seqs_1hot[worker_mask, :, :]
    self.gene_seqs = [self.gene_seqs[si] for si in range(self.num_seqs) if worker_mask[si]]
    self.num_seqs = len(self.gene_seqs)

    # hash remaining gene sequences
    seq_hash = set()
    for gene_seq in self.gene_seqs:
      seq_hash.add( (gene_seq.chrom, gene_seq.start) )

    # filter TSSs
    worker_tss = []
    for tss in self.tss:
      tss_seq_key = (tss.gene_seq.chrom, tss.gene_seq.start)
      if tss_seq_key in seq_hash:
        worker_tss.append(tss)
    self.tss = worker_tss

    # tss_targets isn't relevant for SED


  def __exit__(self):
    # close HDF5
    self.genes_hdf5_in.close()
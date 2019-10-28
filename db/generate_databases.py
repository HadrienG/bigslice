#!/usr/bin/env python3

"""
generate pHMM databases required by BIGSSCAPE to do its
feature extractions

"""

from os import path, makedirs, remove
from shutil import copy
from hashlib import md5
import urllib.request
import gzip
import csv
import subprocess
from Bio import AlignIO


# default parameters
_PFAM_DATABASE_URL = "ftp://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam31.0/Pfam-A.hmm.gz"


def main():
	dir_path = path.abspath(path.dirname(__file__))
	tmp_dir_path = path.join(dir_path, "tmp")
	biosyn_pfam_tsv = path.join(dir_path, "biosynthetic_pfams", "biopfam.tsv")
	biosyn_pfam_hmm = path.join(dir_path, "biosynthetic_pfams", "Pfam-A.biosynthetic.hmm")
	biosyn_pfam_md5sum_path = path.splitext(biosyn_pfam_tsv)[0] + ".md5sum"
	biosyn_pfam_md5sum = md5sum(biosyn_pfam_tsv)
	sub_pfams_tsv = path.join(dir_path, "sub_pfams", "corepfam.tsv")
	sub_pfams_hmms = path.join(dir_path, "sub_pfams", "hmm")
	sub_pfams_md5sum = md5sum(sub_pfams_tsv)
	sub_pfams_md5sum_path = path.splitext(sub_pfams_tsv)[0] + ".md5sum"

	# create temporary directory
	if not path.exists(tmp_dir_path):
	    makedirs(tmp_dir_path)

	# create subpfam directory
	if not path.exists(sub_pfams_hmms):
	    makedirs(sub_pfams_hmms)

	# check if Pfam-A.biosynthetic.hmm exists
	if not path.exists(biosyn_pfam_hmm):

		# (down)loads Pfam-A.hmm
		if not path.exists(path.join(tmp_dir_path, "Pfam-A.hmm.gz")):
			print("Downloading Pfam-A.hmm.gz...")
			urllib.request.urlretrieve(_PFAM_DATABASE_URL, path.join(tmp_dir_path, "Pfam-A.hmm.gz"))

		# load biosynthetic pfams list
		biosynthetic_pfams = []
		with open(biosyn_pfam_tsv, "r") as biopfam_tsv:
			reader = csv.DictReader(biopfam_tsv, dialect="excel-tab")
			for row in reader:
				if row["Status"] == "included":
					biosynthetic_pfams.append(row["Acc"])


		# apply biosynthetic pfams filtering
		with gzip.open(path.join(tmp_dir_path, "Pfam-A.hmm.gz"), "rt") as pfam:
			with open(biosyn_pfam_hmm, "w") as biopfam:
				print("Generating Pfam-A.biosynthetic.hmm...")
				temp_buffer = "" # for saving a temporary hmm entry
				skipping = False
				for line in pfam:
					if line.startswith("//") and len(temp_buffer) > 0: # flush
						if not skipping:
							biopfam.write(temp_buffer)
						temp_buffer = ""
						skipping = False
					if skipping:
						continue
					temp_buffer += line
					if line.startswith("ACC "):
						pfam_acc = line.split(" ")[-1].rstrip()
						try:
							biosynthetic_pfams.remove(pfam_acc)
						except:
							skipping = True

		assert len(biosynthetic_pfams) == 0

	else:
		# check md5sum
		if not path.exists(biosyn_pfam_md5sum_path):
			print("{} exists but no md5sum file found, please check or remove the old hmm file!".format(biosyn_pfam_hmm ))
			raise
		else:
			with open(biosyn_pfam_md5sum_path, "r") as f:
				old_md5sum = f.readline().rstrip()
				if old_md5sum != biosyn_pfam_md5sum:
					print("{} exists but the md5sum is not the same, please check or remove the old hmm file!".format(biosyn_pfam_hmm ))
					raise
		print("Pfam-A.biosynthetic.hmm exists!")

	# update md5sum
	with open(biosyn_pfam_md5sum_path, "w") as f:
		f.write(biosyn_pfam_md5sum)

	# build subpfams
	with open(sub_pfams_tsv, "r") as corepfam:
		corepfam.readline()
		for line in corepfam:
			[pfam_accession, pfam_name, pfam_desc] = line.rstrip().split("\t")
			subpfam_hmm_path = path.join(sub_pfams_hmms, "{}.subpfams.hmm".format(pfam_accession))
			if not path.exists(subpfam_hmm_path):
				print("Building {}...".format(subpfam_hmm_path))
				aligned_multifasta_path = fetch_alignment_file(pfam_accession, tmp_dir_path)
				temp_hmm_path = path.splitext(aligned_multifasta_path)[0] + ".subpfams.hmm"
				if not path.exists(temp_hmm_path):
					tree_path = path.splitext(aligned_multifasta_path)[0] + ".newick"
					if path.exists(tree_path):
						remove(tree_path)
					if subprocess.call(["build_subpfam", "-o", tmp_dir_path, aligned_multifasta_path]) > 0:
						raise
				copy(temp_hmm_path, subpfam_hmm_path)
			else:
				print("Found {}".format(subpfam_hmm_path))

	# update md5sum
	with open(sub_pfams_md5sum_path, "w") as f:
		f.write(sub_pfams_md5sum)


def fetch_alignment_file(pfam_accession, folder_path):
	file_name = path.join(folder_path, "{}-alignment".format(pfam_accession.split(".")[0]))
	stockholm_path = "{}.stockholm".format(file_name)
	multifasta_path = "{}.fa".format(file_name)
	# get rp15 stockholm file
	if not path.exists(stockholm_path):
		url_download = "http://pfam.xfam.org/family/{}/alignment/rp15".format(pfam_accession.split(".")[0])
		print("Downloading from {}...".format(url_download))
		urllib.request.urlretrieve(url_download, stockholm_path)
	else:
		print("Found {}".format(stockholm_path))
	# convert to multifasta
	if not path.exists(multifasta_path):
		AlignIO.convert(stockholm_path, "stockholm", multifasta_path, "fasta")
	return multifasta_path


def md5sum(filename):
    hash = md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(128 * hash.block_size), b""):
            hash.update(chunk)
    return hash.hexdigest()


if __name__ == "__main__":
    main()
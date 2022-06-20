#!/usr/bin/python
#Title			: helper.py
#Usage			: python helper.py -h
#Author			: pmorvalho
#Date			: May 02, 2022
#Description    	: Script with generic functions used in several scripts
#Notes			: 
#Python Version: 3.8.5
# (C) Copyright 2022 Pedro Orvalho.
#==============================================================================

from __future__ import print_function
import sys, os
import re
from copy import deepcopy
import argparse
from sys import argv
from shutil import copyfile

from numpy import binary_repr
import pickle
import gzip
import pathlib
# This is not required if you've installed pycparser into
# your site-packages/ with setup.py
sys.path.extend(['.', '..'])

from pycparser import c_parser, c_ast, parse_file, c_generator

#-----------------------------------------------------------------

id_dict = dict()
cur_id = 0

def reset_ids():
    global id_dict, cur_id
    id_dict = dict()
    cur_id = 0    

def node_id(coord, t=""):
    global id_dict
    global cur_id
    file = coord.file
    line = coord.line
    column = coord.column
    s = file+str(line)+str(column)+str(t)
    # print('node_id')
    # print(s)
    # print(id_dict)
    if s in id_dict.keys():
        return id_dict[s]
    else:
        id_dict[s] = cur_id
        cur_id += 1        
        return id_dict[s]

def node_repr(coord):
    file = coord.file
    line = coord.line
    column = coord.column
    return "l"+str(line)+"-c"+str(column)
    
#-----------------------------------------------------------------
def make_output_dir(input_file, output_dir):
    sincludes = []
    includes = []
    noincludes = []
    with open(input_file, 'r') as reader:
        for line in reader:
            m = re.match('^\s*#\s*include\s*<', line)
            if m:
                sincludes.append(line)
            else:
                m = re.match('^\s*#\s*include', line)
                if m:
                    includes.append(line)
                else:
                    noincludes.append(line)
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    except OSError:
        print("Creation of the directory {0} failed".format(output_dir))

    output_file = output_dir + '/' + os.path.basename(input_file)
    with open(output_file, 'w') as writer:
        writer.writelines(sincludes)
        writer.writelines(includes)
        writer.write('void fakestart() {;}\n')
        writer.writelines(noincludes)

    return output_file, sincludes, includes

def gen_output_file(c_gen, ast, includes, filename, output_dir):
    output_file = output_dir + '/' + filename + ".c"
    str_ast = c_gen.visit(ast)
    # print(str_ast)
    # str_ast = remove_fakestart(str_ast)
    with open(output_file, 'w') as writer:
        writer.writelines(includes)
        writer.write(str_ast)

if __name__ == '__main__':
    pass

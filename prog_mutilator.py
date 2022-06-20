#!/usr/bin/python
#Title			: prog_mutilator.py
#Usage			: python prog_mutilator.py -h
#Author			: pmorvalho
#Date			: May 31, 2022
#Description	        : Program Mutilator - Mutilates programs by: (1) swapping comparison operators; (2) changing the variable being used by another; and (3) deleting expressions from the code. Or applying more than one of these mutilations.
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
from topological_sorting import getTopologicalOrders

from itertools import product, combinations, chain
from numpy import binary_repr
import pickle
import gzip
import pathlib

import random

# This is not required if you've installed pycparser into
# your site-packages/ with setup.py
sys.path.extend(['.', '..'])

from pycparser import c_parser, c_ast, parse_file, c_generator

from helper import *

#-----------------------------------------------------------------

bin_ops_2_swap = {"<" : "<=", ">" : ">=", "<=" : "<", ">=" : ">", "==" : "=", "!=" : "=="}

#-----------------------------------------------------------------
class MutilatorVisitor(c_ast.NodeVisitor):

    def __init__ (self):
        # list with the program variables
        self.scope_vars = dict()
        # number of binary operations to swap
        self.bin_ops_2_swap = list()
        # list of bugs introduced
        self.bugs_list = dict()
        # inside a declaration flag
        self.inside_declaration = False
        # the following is a list of lists of every possible variable misuse one can perform.
        # Each sublist contains for each identifier nodes which are identifiers one can swap and maintain the same type in order for the program to compile.
        self.possible_variable_misuses = list()
        # The list of node_ids of assignments we can safely remove i.e. that are not part of some variable declaration
        self.possible_assignment_deletion = list()
        
    def visit(self, node):
        #node.show()
        return c_ast.NodeVisitor.visit(self, node)

    def visit_FileAST(self, node):
        #print('****************** Found FileAST Node *******************')
        n_ext = []
        fakestart_pos = -1 #for the case of our injected function which do not have the fakestart function in their ast
        for e in range(len(node.ext)):
            x = node.ext[e]
            n_ext.append(self.visit(x))
            if fakestart_pos==-1 and isinstance(x, c_ast.FuncDef) and "fakestart" in x.decl.type.type.declname:
                fakestart_pos=e
                
        
        n_file_ast = c_ast.FileAST(n_ext[fakestart_pos+1:])
        return n_file_ast

    def visit_Decl(self, node):
        # print('****************** Found Decl Node *******************')
        self.inside_declaration = True
        if not isinstance(node.type, c_ast.TypeDecl):
            # because it can be other type of declaration. Like func declarations.
            node.type = self.visit(node.type)
            self.inside_declaration = False
            if isinstance(node.type, c_ast.Enum):
                # Enum are declared in the var_info.h file!
                return
            else:
                return node
        # node.show()
        type = node.type
        if isinstance(type.type, c_ast.Enum):
             # type = type.type.name
            # node.type = self.visit(node.type)
            type = node.type.type
        else:
            type = type.type.names[0]

        self.scope_vars[node.name] = type
        if node.init != None:
            node.init = self.visit(node.init)

        self.inside_declaration = False
        return node


    def visit_ArrayDecl(self, node):
        #print('****************** Found Decl Node *******************')
        # node.show()
        return node

    def visit_Assignment(self, node):
        # print('****************** Found Assignment Node *******************')
        if not self.inside_declaration:
            node_info = node_repr(node.coord)
            self.possible_assignment_deletion.append(node_info)
        node.rvalue = self.visit(node.rvalue)
        node.lvalue = self.visit(node.lvalue)
        return node

    def visit_ID(self, node):
        #print('****************** Found ID Node *******************')
        curr_id = node.name
        if not self.inside_declaration and curr_id in self.scope_vars.keys():
            # if we are not inside a declaration node then it is safe to change this node's id for other variable already declared of the same type.
            # for this we only need to consult the scope_vars map that contains all the variables declared until now and their respective types
            var_type = self.scope_vars[curr_id]
            node_info = node_repr(node.coord)
            var_misuses = []
            for v in self.scope_vars.keys():
                if v == curr_id:
                     continue # we do not want to swap by the same identifier
                if var_type == self.scope_vars[v]:
                    var_misuses.append((node_info, v))

            if var_misuses != []:
                self.possible_variable_misuses.append(var_misuses)
                
        return node

    def visit_Enum(self, node):
        # #print('****************** Found Enum Node *******************')
        # insert each enum on the .h file, after the scope functions of the fakestart function
        return node

    def visit_ExprList(self, node):
        #print('****************** Found ExprList Node *******************')
        for e in node.exprs:
            e = self.visit(e)
        return node

    def visit_UnaryOp(self, node):
        #print('****************** Found Unary Operation *******************')
        node.expr = self.visit(node.expr)
        return node
    
    def visit_BinaryOp(self, node):
        # print('****************** Found Binary Operation *******************')
        # print(node.show())
        left = self.visit(node.left)
        right = self.visit(node.right)
        if node.op in bin_ops_2_swap.keys():
            self.bin_ops_2_swap.append(node_id(node.coord))
        return c_ast.BinaryOp(node.op, left, right, node.coord)

    def visit_TernaryOp(self, node):
        # print('****************** Found Ternary Op Node *******************')
        if_id = node_id(node.coord)
        n_cond = self.visit(node.cond)
        n_iftrue = self.visit(node.iftrue)
        n_iffalse = node.iffalse
        # if there exists and else statement
        if n_iffalse is not None:
            n_iffalse = self.visit(n_iffalse)
        #print('****************** New Cond Node *******************')
        n_ternary =  c_ast.TernaryOp(n_cond, n_iftrue, n_iffalse, node.coord)
        return n_ternary

    def visit_FuncDef(self, node):
        #print('****************** Found FuncDef Node *******************')
        decl = node.decl
        param_decls = node.param_decls
        if "main" != node.decl.name and "fakestart" != node.decl.name: #ignore main function
            # if the function has parameters add them to the scope
            if node.decl.type.args:
                pass
        body = node.body
        coord = node.coord
        n_body_1 = self.visit(body)
        n_func_def_ast = c_ast.FuncDef(decl, param_decls, n_body_1, coord)

        return n_func_def_ast

    def visit_FuncCall(self, node):
        #print('****************** Found FuncCall Node *******************')
        if node.args:
            node.args = self.visit(node.args)
        return c_ast.FuncCall(node.name, node.args, node.coord)

    def visit_ExprList(self, node):
        # print('****************** Found ExprList Node *******************')
        for e in range(len(node.exprs)):
            node.exprs[e] = self.visit(node.exprs[e])
        return node
    
    def visit_ParamList(self, node):
        # print('****************** Found ParamList Node *******************')
        for e in range(len(node.params)):
            node.params[e] = self.visit(node.params[e])
        return node
    
    def visit_Compound(self, node):
        #print('****************** Found Compound Node *******************')
        block_items = node.block_items
        coord = node.coord
        n_block_items = []
        if block_items is not None:
            for x in block_items:
                n_block_items.append(self.visit(x))

        n_compound_ast = c_ast.Compound(n_block_items, coord)
        return n_compound_ast

    def visit_If(self, node):
        #print('****************** Found IF Node *******************')
        if_id = node_id(node.coord)
        n_cond = self.visit(node.cond)
        if isinstance(node.iftrue, c_ast.Compound):
            n_iftrue = self.visit(node.iftrue)
        else:
            n_iftrue = self.visit(c_ast.Compound([node.iftrue], node.iftrue.coord))

        if node.iffalse is not None and not isinstance(node.iffalse, c_ast.Compound):
            node.iffalse = c_ast.Compound([node.iffalse], node.iffalse.coord)
        n_iffalse = self.visit(node.iffalse)
        #print('****************** New Cond Node *******************')
        n_if = c_ast.If(n_cond, n_iftrue, n_iffalse, node.coord)
        return n_if

    def visit_For(self, node):
        # print('****************** Found For Node *******************')
        for_id = node_id(node.coord)
        n_init = self.visit(node.init)
        n_cond = self.visit(node.cond)
        if not isinstance(node.stmt, c_ast.Compound):
            node.stmt = c_ast.Compound([node.stmt], node.stmt.coord)
        n_stmt = self.visit(node.stmt)
        n_next = self.visit(node.next)
        # We dont need to put a scope_info at the end of the for because the compound node already does that
        n_for = c_ast.For(n_init, n_cond, n_next, n_stmt, node.coord)
        return n_for

    def visit_While(self, node):
        #print('****************** Found While Node *******************')
        while_id = node_id(node.coord)
        n_cond = self.visit(node.cond)
        n_stmt = self.visit(node.stmt)
        n_while = c_ast.While(c_ast.ExprList([n_cond]), n_stmt, node.coord)
        return n_while

    def visit_Continue(self, node):
        # print('****************** Found Continue Node *******************')
        return node

    def generic_visit(self, node):
        #print('******************  Something else ************')
        return node
    
#-----------------------------------------------------------------
# A visitor that swaps the comparison operators of simple binary comparisons >, < <=, >=
class SwapBinOpsVisitor(MutilatorVisitor):

    def __init__ (self, bin_ops_2_swap_ids):
        super().__init__()
        # bin_ops_2_swap is a list of booleans that says if each binary operation is to swap or not
        self.bin_ops_2_swap_ids = bin_ops_2_swap_ids
        
    def visit(self, node):
        return MutilatorVisitor.visit(self, node)

    def visit_BinaryOp(self, node):
        # print('****************** Found Binary Operation *******************')
        # print(node.show())
        left = self.visit(node.left)
        right = self.visit(node.right)
        if node.op in bin_ops_2_swap.keys() and node_id(node.coord) in self.bin_ops_2_swap_ids:
            self.bugs_list[node_repr(node.coord)] = ("BinaryOp-"+node.op, "BinaryOp-"+bin_ops_2_swap[node.op])
            return c_ast.BinaryOp(bin_ops_2_swap[node.op], left, right, node.coord)
        return c_ast.BinaryOp(node.op, left, right, node.coord)

#-----------------------------------------------------------------
# A visitor that introduces a bug of variable misuse i.e., changes the name of some variable occurrence by another variable's identifier
class VariableMisuseVisitor(MutilatorVisitor):
    def __init__ (self, var_2_misused):
        super().__init__()
        self.var_2_misused, self.new_var = var_2_misused
        
    def visit(self, node):
        return MutilatorVisitor.visit(self, node)

    def visit_ID(self, node):
        #print('****************** Found ID Node *******************')
        node_info = node_repr(node.coord)
        if node_info == self.var_2_misused:
            self.bugs_list[node_repr(node.coord)] = ("VarMisuse-"+node.name, "VarMisuse-"+self.new_var)
            node.name = self.new_var
                
        return node

#-----------------------------------------------------------------
#A visitor that introduces the bug of a missing expression in the program in our case we delete assignments that are not related to variables' declarations 
class AssignmentDeletionVisitor(MutilatorVisitor):
    def __init__ (self, expr_2_delete):
        super().__init__()
        self.expr_2_delete = expr_2_delete
        
    def visit(self, node):
        return MutilatorVisitor.visit(self, node)

    def visit_Assignment(self, node):
        # print('****************** Found Assignment Node *******************')
        node_info = node_repr(node.coord)
        if node_info == self.expr_2_delete:
            self.bugs_list[node_info] = ("AssignmentDeletion",str(node))
            return None
        node.rvalue = self.visit(node.rvalue)
        node.lvalue = self.visit(node.lvalue)
        return node

#-----------------------------------------------------------------

def gen_variable_mappings(var_maps, bn, corr_impl_id, output_dir):
    var_dict = dict()
    other_d = var_maps[corr_impl_id]   # the correct program
    d = var_maps[bn]
    for v in other_d.keys():
        if v in d.keys() and d[v] == other_d[v] and v not in var_dict.keys():
            var_dict[v] = v
        elif v not in d.keys() and v not in var_dict.keys():
            var_dict[v] = "UnkVar"

    for v in d.keys():
        if v in other_d.keys() and d[v] == other_d[v] and v not in var_dict.keys():
            var_dict[v] = v
        elif v not in other_d.keys() and v not in var_dict.keys():
            var_dict["UnkVar"] = v

    p_name = output_dir+'/var_map-{bn1}_{bn2}.pkl.gz'.format(bn1=corr_impl_id, bn2=bn)
    fp=gzip.open(p_name,'wb')
    pickle.dump(var_dict,fp)
    fp.close()

def save_bugs_map(bugs_maps, bn, corr_impl_id, output_dir):
    p_name = output_dir+'/bug_map-{bn1}-{bn2}.pkl.gz'.format(bn1=corr_impl_id, bn2=bn)
    fp=gzip.open(p_name,'wb')
    pickle.dump(bugs_maps[bn],fp)
    fp.close()
    
def get_prog_name(bops, var_mu, exp_del):
    # based on the users' arguments the name of the program will contain information about the mutations required
    p_name = ""
    p_name = bops+"-" if args.comp_ops or args.all_mut else p_name
    p_name = p_name+var_mu+"-" if args.var_mu or args.all_mut else p_name
    p_name = p_name+exp_del+"-" if args.asg_del or args.all_mut else p_name
    return p_name[:-1]
    
def instrument_file(input_file, output_dir):
    output_file, sincludes, includes = make_output_dir(input_file, output_dir)#, logfilename, loglibpath)
    try:
        ast = parse_file(output_file, use_cpp=True,
            cpp_path='gcc',
            cpp_args=['-E', '-Iutils/fake_libc_include'])
    except:
        return

    # print('******************** INPUT FILE: ********************')
    v = c_ast.NodeVisitor()
    v.visit(ast)
    # ast.show()
    # exit()
    # v = VariablesVisitor()
    v = MutilatorVisitor()
    gen = c_generator.CGenerator ()
    n_ast = v.visit(ast)
    # n_ast.show()
    # return
    if args.verbose:
        print()
        print(input_file)
        print("Variables :", v.scope_vars)
        print("Number of BinOps of interest:", len(v.bin_ops_2_swap))
        print("Number of possible locations where we can misuse variables", len(v.possible_variable_misuses))
        print("Number of assignment expressions safe to delete:", len(v.possible_assignment_deletion))

    n_mutilations = int(args.num_mut)    
    bin_ops_2_swap = list([[]])
    if args.comp_ops or args.all_mut:
        if args.single:
            bin_ops_2_swap += random.sample(v.bin_ops_2_swap, min(n_mutilations, len(v.bin_ops_2_swap)))
        else:
            bin_ops_2_swap += list(combinations(v.bin_ops_2_swap, min(n_mutilations, len(v.bin_ops_2_swap))))

    variable_misuses = list([(None, None)]) # To generatre the correct program without any bug introduced as the first program
    if args.var_mu or args.all_mut:
        if args.num_mut > 1:
            exit("Currently this program can only perform 1 mutilation per program for the variable misuse task. The user is asking for {m} mutilations!".format(m=args.num_mut))
        variable_misuses += list(chain(*v.possible_variable_misuses))
        if args.single:
            variable_misuses = [(None,None)] + random.sample(variable_misuses[1:], min(n_mutilations, len(variable_misuses)))

        if args.verbose:
            print(" #Variable misuse possibilities: ", len(variable_misuses))

    assignments_2_delete = list([[]])
    if args.asg_del or args.all_mut:
        if args.single:
            assignments_2_delete += random.sample(v.possible_assignment_deletion, min(n_mutilations, len(v.possible_assignment_deletion)))
        else:
            assignments_2_delete += list(v.possible_assignment_deletion)

    if args.info:
        total_progs = len(bin_ops_2_swap)*len(variable_misuses)*len(assignments_2_delete)
        return total_progs
            
    var_maps = dict()
    prev_nums = list()
    bugs_map = dict()
    corr_impl_id = None
    for b in range(len(bin_ops_2_swap)):
        b_id = str(b).rjust(len(str(len(bin_ops_2_swap))), '0')
        for vm in range(len(variable_misuses)):
            var_misused = variable_misuses[vm]
            vm_id = str(vm).rjust(len(str(len(variable_misuses))), '0')
            for ad in range(len(assignments_2_delete)):
                exp = assignments_2_delete[ad]
                exp_id = str(ad).rjust(len(str(len(assignments_2_delete))), '0')
                # b_ast = parse_file(output_file, use_cpp=True, cpp_path='gcc', cpp_args=['-E', '-Iutils/fake_libc_include'])
                prev_nums.append(get_prog_name(b_id, vm_id, exp_id))
                curr_num = prev_nums[-1]
                if corr_impl_id is None:
                    corr_impl_id = curr_num
                if args.comp_ops or args.all_mut:
                    v_h = SwapBinOpsVisitor(bin_ops_2_swap[b])
                    b_ast = v_h.visit(n_ast)
                    var_maps[curr_num] = v.scope_vars
                    bugs_map[curr_num] = v_h.bugs_list
                if args.var_mu or args.all_mut:
                    v_h = VariableMisuseVisitor(var_misused)
                    b_ast = v_h.visit(n_ast)
                    var_maps[curr_num] = v.scope_vars
                    bugs_map[curr_num] = bugs_map[curr_num] | v_h.bugs_list if curr_num in bugs_map.keys() else v_h.bugs_list
                if args.asg_del or args.all_mut:
                    v_h = AssignmentDeletionVisitor(exp)
                    b_ast = v_h.visit(n_ast)
                    var_maps[curr_num] = v.scope_vars
                    bugs_map[curr_num] = bugs_map[curr_num] | v_h.bugs_list if curr_num in bugs_map.keys() else v_h.bugs_list                    

                if args.verbose:
                    print("Bug mapping:", curr_num, bugs_map[curr_num])
                gen_output_file(gen, b_ast, sincludes + includes, curr_num, output_dir)
                gen_variable_mappings(var_maps, curr_num, corr_impl_id, output_dir)
                save_bugs_map(bugs_map, curr_num, corr_impl_id, output_dir)                    
    os.system("rm "+output_file)
    
#-----------------------------------------------------------------

def gen_program_mutilations(progs_dir, output_dir):
    total_progs = 0
    progs = list(pathlib.Path(progs_dir).glob('*.c'))
    progs = random.sample(progs, min(args.num_progs_2_process, len(progs)))
    for p in progs:
        stu_id = str(p).split("/")[-1][:-2] # to remove the .c
        if args.verbose:
            print("Dealing with program ", stu_id)
        s_mutils = instrument_file(p, output_dir+"/"+stu_id)
        if args.info and s_mutils is not None:
           total_progs += s_mutils
    if args.info:
        print(total_progs)
        os.system("rm -rf "+output_dir)
        
#-----------------------------------------------------------------

def parser():
    parser = argparse.ArgumentParser(prog='prog_mutilator.py', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-c', '--comp_ops', action='store_true', default=False, help='Swaps the comparison operators.')
    parser.add_argument('-vm', '--var_mu', action='store_true', default=False, help='Introduces a bug of variable misuse.')
    parser.add_argument('-ad', '--asg_del', action='store_true', default=False, help='Introduces a bug of expression deletion (assignments).')    
    parser.add_argument('-a', '--all_mut', action='store_true', default=False, help='Performs all the mutilations above.')
    parser.add_argument('-s', '--single', action='store_true', default=False, help='Generates a single erroneous programs, instead of enumerating all possibilities.')
    parser.add_argument('-n', '--num_mut', type=int, default=1, help='Number of mutilations to be performed. (Default = 1).')
    parser.add_argument('-pp', '--num_progs_2_process', type=int, default=50, help='Number of programs to process from the input directory. (Default = 50).')
    parser.add_argument('-info', '--info', action='store_true', default=False, help='Prints the total number of programs the required mutilations can produced and exits without producing the sets of programs.')
    parser.add_argument('-d', '--input_dir', help='Name of the input directory.')
    parser.add_argument('-o', '--output_dir', help='Name of the output directory.')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Prints debugging information.')
    args = parser.parse_args(argv[1:])
    return args


if __name__ == "__main__":
    args = parser()
    if len(sys.argv) >= 2:
        input_dir = args.input_dir
        output_dir = args.output_dir
        gen_program_mutilations(input_dir, output_dir)
    else:
        print('python {0} -h'.format(sys.argv[0]))
        

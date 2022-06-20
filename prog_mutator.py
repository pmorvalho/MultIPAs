#!/usr/bin/python
#Title			: prog_mutator.py
#Usage			: python prog_mutator.py -h
#Author			: pmorvalho
#Date			: April 29, 2022
#Description     	: A visitor for C programs based on pycparser, that mutates programs based on some specific rules.
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

from itertools import product
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

bin_ops_2_swap = {"<" : ">", ">" : "<", "<=" : ">=", ">=" : "<=", "==" : "==", "!=" : "!="}
incr_decr_ops = {"p++" : "++", "++" : "p++", "--" : "p--", "p--" : "--"}

#-----------------------------------------------------------------
class MutatorVisitor(c_ast.NodeVisitor):

    def __init__ (self):
        # list with the program variables
        self.scope_vars = dict()
        # number of binary operations to swap
        self.num_bin_ops_2_swap = 0
        # coords of the if nodes to swap
        self.if_2_swap_ids = list()
        # flag to use while checking an if-statement
        self.check_simple_if_else = False
        # coord of the increment/decrement nodes to swap
        self.inc_ops_2_swap_ids = list()
        # flag to check if the increment/decrement operator is being used inside an assignment or a binary op
        self.safe_inc_op = 1
        # dict with infromations about the variables declared inside each scope
        self.blocks_vars = dict()
        # flag to know if we are inside a variable declaration
        self.declaring_var = False
        # variable to know the coord of the current block
        self.curr_block = "global"
        # variable to know the name of the current variable being declared
        self.curr_var = None
        # info aboout the variable declaration for each code block
        self.blocks_vars[self.curr_block] = dict()
        self.blocks_vars[self.curr_block]["decls_id"] = []
        self.blocks_vars[self.curr_block]["var_2_coord"] = dict()
        self.blocks_vars[self.curr_block]["decls_dependencies"] = []
        self.blocks_vars[self.curr_block]["permutations"] = []
        # translating for-loops into while-loops
        self.found_continue = False
        self.for_ids_2_swap = []
        
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
        if self.blocks_vars[self.curr_block]["decls_id"] == []:
            del self.blocks_vars[self.curr_block]
        return n_file_ast

    def visit_Decl(self, node):
        # print('****************** Found Decl Node *******************')
        if not isinstance(node.type, c_ast.TypeDecl):
            # because it can be other type of declaration. Like func declarations.
            node.type = self.visit(node.type)
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

        if self.curr_block is not None:
            self.blocks_vars[self.curr_block]["decls_id"].append(node_id(node.coord))
            self.blocks_vars[self.curr_block]["var_2_coord"][node.name] = node_id(node.coord)
        self.scope_vars[node.name] = type
        self.curr_var = node.name
        if node.init != None:
            node.init = self.visit(node.init)

        self.curr_var = None

        return node


    def visit_ArrayDecl(self, node):
        #print('****************** Found Decl Node *******************')
        # node.show()
        return node

    def visit_Assignment(self, node):
        # print('****************** Found Assignment Node *******************')
        self.safe_inc_op -= 1
        node.rvalue = self.visit(node.rvalue)
        node.lvalue = self.visit(node.lvalue)
        self.safe_inc_op += 1
        return node

    def visit_ID(self, node):
        #print('****************** Found ID Node *******************')
        if self.curr_var is not None and node.name in self.blocks_vars[self.curr_block]["var_2_coord"].keys():
            self.blocks_vars[self.curr_block]["decls_dependencies"].append((self.blocks_vars[self.curr_block]["var_2_coord"][node.name],  self.blocks_vars[self.curr_block]["var_2_coord"][self.curr_var]))
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
        if self.safe_inc_op == 1 and node.op in incr_decr_ops.keys():
            self.inc_ops_2_swap_ids.append(node.coord)
        node.expr = self.visit(node.expr)
        return node
    
    def visit_BinaryOp(self, node):
        # print('****************** Found Binary Operation *******************')
        # print(node.show())
        self.safe_inc_op -= 1
        left = self.visit(node.left)
        right = self.visit(node.right)
        self.safe_inc_op += 1
        if node.op in bin_ops_2_swap.keys():
            self.num_bin_ops_2_swap += 1
        return c_ast.BinaryOp(node.op, left, right, node.coord)

    def visit_TernaryOp(self, node):
        # print('****************** Found Ternary Op Node *******************')
        if_id = node_id(node.coord)
        self.if_2_swap_ids.append(if_id)
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
        coord = node_id(node.coord)
        self.curr_block = str(coord)
        self.blocks_vars[self.curr_block] = dict()
        self.blocks_vars[self.curr_block]["decls_id"] = []
        self.blocks_vars[self.curr_block]["var_2_coord"] = dict()
        self.blocks_vars[self.curr_block]["decls_dependencies"] = []
        self.blocks_vars[self.curr_block]["permutations"] = []
        n_block_items = []
        if block_items is not None:
            for x in block_items:
                if isinstance(x, c_ast.Decl) and isinstance(x.type, c_ast.TypeDecl):
                    self.declaring_var = True

                n_block_items.append(self.visit(x))
                
                self.declaring_var = False
                self.curr_block = str(coord)

        self.blocks_vars[self.curr_block]["permutations"] = getTopologicalOrders(self.blocks_vars[self.curr_block]["decls_id"], self.blocks_vars[self.curr_block]["decls_dependencies"])
        # print(self.blocks_vars[coord]["var_2_coord"])
        # print(self.blocks_vars[coord]["decls_dependencies"])
        # print(len(self.blocks_vars[coord]["permutations"]))
        # print(self.blocks_vars[coord]["permutations"])
        if self.blocks_vars[self.curr_block]["decls_id"] == []:
            del self.blocks_vars[self.curr_block]

        self.curr_block = "global"
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
        if self.check_simple_if_else:
            self.check_simple_if_else = False
        else:
            self.check_simple_if_else = True

        if node.iffalse is not None and not isinstance(node.iffalse, c_ast.Compound):
            node.iffalse = c_ast.Compound([node.iffalse], node.iffalse.coord)
        n_iffalse = self.visit(node.iffalse)
        # if there exists and else statement
        if n_iffalse is not None and self.check_simple_if_else:
            self.if_2_swap_ids.append(if_id)
        # if is just an if without and else or if we already saved the id of the node we can turn off the flag. 
        self.check_simple_if_else = False
        #print('****************** New Cond Node *******************')
        n_if = c_ast.If(n_cond, n_iftrue, n_iffalse, node.coord)
        return n_if

    def visit_For(self, node):
        # print('****************** Found For Node *******************')
        for_id = node_id(node.coord)
        n_init = self.visit(node.init)
        n_cond = self.visit(node.cond)
        self.find_continue = False
        if not isinstance(node.stmt, c_ast.Compound):
            node.stmt = c_ast.Compound([node.stmt], node.stmt.coord)
        n_stmt = self.visit(node.stmt)
        if self.found_continue:
            self.found_continue = False
        else:
            self.for_ids_2_swap.append(for_id)            
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
        self.found_continue = True
        return node

    def generic_visit(self, node):
        #print('******************  Something else ************')
        return node
    
#-----------------------------------------------------------------
# A visitor that swaps the arguments of binary operators such as >, < <=, >=
class SwapBinOpsVisitor(MutatorVisitor):

    def __init__ (self, bin_ops_2_swap):
        super().__init__()
        # bin_ops_2_swap is a list of booleans that says if each binary operation is to swap or not
        self.bin_ops_2_swap = bin_ops_2_swap
        
    def visit(self, node):
        return MutatorVisitor.visit(self, node)

    def visit_BinaryOp(self, node):
        # print('****************** Found Binary Operation *******************')
        # print(node.show())
        left = self.visit(node.left)
        right = self.visit(node.right)
        if node.op in bin_ops_2_swap.keys() and len(self.bin_ops_2_swap) > 0:
            if self.bin_ops_2_swap[0]:
                self.bin_ops_2_swap.pop(0)
                return c_ast.BinaryOp(bin_ops_2_swap[node.op], right, left, node.coord)
            else:
                self.bin_ops_2_swap.pop(0)
                
        return c_ast.BinaryOp(node.op, left, right, node.coord)

#-----------------------------------------------------------------
# A visitor that swaps the simple if-statements by negating its test condition and swapping the if-block with the else-block.
class SwapIfElseVisitor(MutatorVisitor):

    def __init__ (self, ifs_2_swap, if_ids):
        super().__init__()
        self.ifs_2_swap = ifs_2_swap
        self.ifs_ids = if_ids
        
    def visit(self, node):
        return MutatorVisitor.visit(self, node)

    def visit_If(self, node):
        #print('****************** Found IF Node *******************')
        if_id = node_id(node.coord)
        n_cond = self.visit(node.cond)
        n_iftrue = self.visit(node.iftrue)
        n_iffalse = self.visit(node.iffalse)
        # if there exists and else statement
        if if_id in self.ifs_ids and len(self.ifs_2_swap) > 0:
            if self.ifs_2_swap[0]:
                self.ifs_2_swap.pop(0)
                return c_ast.If(c_ast.UnaryOp("!", n_cond, node.coord) , n_iffalse, n_iftrue, node.coord)
            self.ifs_2_swap.pop(0)
        n_if = c_ast.If(n_cond, n_iftrue, n_iffalse, node.coord)
        return n_if

    def visit_TernaryOp(self, node):
        # print('****************** Found Ternary Op Node *******************')
        if_id = node_id(node.coord)
        n_cond = self.visit(node.cond)
        n_iftrue = self.visit(node.iftrue)
        n_iffalse = self.visit(node.iffalse)        
        if if_id in self.ifs_ids and len(self.ifs_2_swap) > 0:
            if self.ifs_2_swap[0]:
                self.ifs_2_swap.pop(0)
                return c_ast.TernaryOp(c_ast.UnaryOp("!", n_cond, node.coord), n_iffalse, n_iftrue, node.coord)
            self.ifs_2_swap.pop(0)
        return c_ast.TernaryOp(n_cond, n_iftrue, n_iffalse, node.coord)

#-----------------------------------------------------------------
# A visitor that swaps the increment/decrement operators (++, --) when these are not being used inside an assignment or a binary operation.
class SwapIncrDecrOpsVisitor(MutatorVisitor):
    def __init__ (self, inc_ops_2_swap, inc_ops_ids):
        super().__init__()
        self.inc_ops_2_swap = inc_ops_2_swap
        self.inc_ops_ids = inc_ops_ids
        
    def visit(self, node):
        return MutatorVisitor.visit(self, node)

    def visit_UnaryOp(self, node):
        # print('****************** Found Binary Operation *******************')
        # print(node.show())
        expr = self.visit(node.expr)
        if node.op in incr_decr_ops.keys() and len(self.inc_ops_2_swap) > 0:
            if self.inc_ops_2_swap[0]:
                self.inc_ops_2_swap.pop(0)
                return c_ast.UnaryOp(incr_decr_ops[node.op], expr, node.coord)
            else:
                self.inc_ops_2_swap.pop(0)
                
        return c_ast.UnaryOp(node.op, expr, node.coord)


#-----------------------------------------------------------------
# A visitor that declares a new dummy variable in the main's block. A variable that is not used througout the program.
class DeclDumVarVisitor(MutatorVisitor):
    def __init__ (self, vars_set, new_var=True):
        super().__init__()
        self.new_var = new_var
        self.vars_set = vars_set
        
    def visit(self, node):
        return MutatorVisitor.visit(self, node)

    def visit_FuncDef(self, node):
        #print('****************** Found FuncDef Node *******************')
        body = node.body
        coord = node.coord
        if "main" == node.decl.name and self.new_var:
            last_decl = -1
            # each functions definition has a compound node inside a compound node for some reason.
            # that why we are using body.block_items[0].block_items
            for i in range(len(body.block_items)):
                x = body.block_items[i]
                if isinstance(x, c_ast.Compound):
                    for j in range(len(x.block_items)):
                        z = x.block_items[j]
                        if isinstance(z, c_ast.Decl) and isinstance(z.type, c_ast.TypeDecl):
                            last_decl = j
                            continue
                        else:
                            break
                    new_var_name = gen_fresh_var_name(self.vars_set, "int")
                    body.block_items[i].block_items.insert(last_decl+1, c_ast.Decl(name=new_var_name,
                        quals=[],
                        storage=[],
                        funcspec=[],
                        align=[],
                        type=c_ast.TypeDecl(new_var_name, quals=[], align=[], type=c_ast.IdentifierType(['int']), coord=node.coord),
                        init=None,
                        bitsize=None ,
                        coord=None))
                else:
                    if isinstance(x, c_ast.Decl) and isinstance(x.type, c_ast.TypeDecl):
                        last_decl = i
                        continue
                    else:
                        new_var_name = gen_fresh_var_name(self.vars_set, "int")
                        body.block_items.insert(last_decl+1, c_ast.Decl(name=new_var_name,
                        quals=[],
                        storage=[],
                        funcspec=[],
                        align=[],
                        type=c_ast.TypeDecl(new_var_name, quals=[], align=[], type=c_ast.IdentifierType(['int']), coord=node.coord),
                        init=None,
                        bitsize=None ,
                        coord=None))
                        break
        n_body = self.visit(body)
        n_func_def_ast = c_ast.FuncDef(node.decl, node.param_decls, n_body, coord)
        return n_func_def_ast

#-----------------------------------------------------------------
# A visitor that reorder the variable declarations in a program based on the provided topological sorting.
class ReorderVarDeclsVisitor(MutatorVisitor):
    def __init__ (self, blocks_reordering):
        super().__init__()
        self.blocks_reordering = blocks_reordering
        
    def visit(self, node):
        return MutatorVisitor.visit(self, node)

    def visit_Compound (self, node):
        #print('****************** Found Compound Node *******************')
        block_items = node.block_items
        coord = node_id(node.coord)
        n_block_items = []
        if block_items is not None:
            if str(coord) in self.blocks_reordering.keys():
                last_decl = 0
                for i in range(len(block_items)):
                    x = block_items[i]
                    if isinstance(x, c_ast.Decl) and isinstance(x.type, c_ast.TypeDecl):
                        last_decl = i
                        continue
                    else:
                        break
                new_order = []
                for d in self.blocks_reordering[str(coord)]:
                    for x in block_items:
                        if str(node_id(x.coord)) == str(d):
                            new_order.append(x)
                            break
                # block_items = new_order + block_items[last_decl:] if args.dummy_var or args.all_mut else new_order + block_items[last_decl+1:]
                block_items = new_order + block_items[last_decl+1:]
                
            for x in block_items:
                n_block_items.append(self.visit(x))
                
        n_compound_ast = c_ast.Compound(n_block_items, node.coord)
        return n_compound_ast

def get_possible_blocks_permutations(blocks_info):
    blocks = []
    num_decls_per_block = []
    blocks_permutations = []
    for b in blocks_info.keys():
        blocks.append(b)
        blocks_permutations.append(blocks_info[b]["permutations"])
        num_decls_per_block.append(range(len(blocks_permutations[-1])))
        
    permutations = list(product(*num_decls_per_block))
    blocks_reorderings = []    
    for p in permutations:
        d = dict()
        for b in range(len(p)):
            # b is the position of the block we are dealing with  
            i = p[b] # i is the permuation i of block n 
            d[str(blocks[b])] = blocks_permutations[b][i]
        blocks_reorderings.append(d)

    if blocks_reorderings == []:
        return [list()]
    return blocks_reorderings

#-----------------------------------------------------------------
# A visitor that translates simple for-loops (without any continue instruction) into a while-loop
class For2WhileVisitor(MutatorVisitor):
    def __init__ (self, fors_2_swap, fors_ids_2_swap):
        super().__init__()
        self.fors_2_swap = fors_2_swap
        self.fors_ids_2_swap = fors_ids_2_swap
        
    def visit(self, node):
        return MutatorVisitor.visit(self, node)

    def visit_Compound(self, node):
        #print('****************** Found Compound Node *******************')
        block_items = node.block_items
        coord = node.coord
        n_block_items = []
        if block_items is not None:
            for i in range(len(block_items)):
                x = block_items[i]
                if isinstance(x, c_ast.For) and (node_id(x.coord) in self.fors_ids_2_swap) and len(self.fors_2_swap) > 0:
                    if self.fors_2_swap[0]:
                        self.fors_2_swap.pop(0)
                        n_block_items.append(self.visit(x.init))
                        if isinstance(x.stmt, c_ast.Compound):
                            x.stmt.block_items.append(x.next)
                            n_block_items.append(self.visit(c_ast.While(x.cond, x.stmt, coord=x.coord)))                   
                        else:
                            n_block_items.append(self.visit(c_ast.While(x.cond, c_ast.Compound([x.stmt, x.next], coord=x.coord), coord=x.coord)))                        
                    else:
                        self.fors_2_swap.pop(0)
                        n_block_items.append(self.visit(x))
                else:
                    n_block_items.append(self.visit(x))
                
        n_compound_ast = c_ast.Compound(n_block_items, coord)
        return n_compound_ast

#-----------------------------------------------------------------

def gen_binary_lists(num_ops):
    # Given a natural number num_ops, returns a lists of list of booleans.
    # each sublist corresponds to a binary number from 0 to num_ops
    # the binary number is represented as boolean values e.g. 10 -> ["10", ["True", "False"]]
    bin_lists = []
    # w = len(binary_repr(num_ops))
    w = num_ops
    for n in range(2**(num_ops)):
        bl = []
        bn = binary_repr(n, width=w)
        for b in bn:
            if b == "0":
                bl.append(False)
            elif b == "1":
                bl.append(True)
        bin_lists.append([bn,bl])
    return bin_lists

def gen_fresh_var_name(var_maps, t):
    for i in range(len(var_maps.keys())):
        n_v = "_{t}_{i}_".format(t=t, i=i)
        if n_v in var_maps.keys():
            continue
        return n_v

def gen_variable_mappings(var_maps, bn, bin_numbers, output_dir):
    # for bn_a in bin_numbers:
    #     if bn_a == bn:
    #         break
    bn_a = bin_numbers[0]
    var_dict = dict()
    other_d = var_maps[bn_a]
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

    p_name = output_dir+'/var_map-{bn1}_{bn2}.pkl.gz'.format(bn1=bn_a, bn2=bn)
    fp=gzip.open(p_name,'wb')
    pickle.dump(var_dict,fp)
    fp.close()

def get_prog_name(bops, bifs, biops, dv, block, fors):
    # based on the users' arguments the name of the program will contain information about the mutations required
    p_name = ""
    p_name = bops+"-" if args.comp_ops or args.all_mut else p_name
    p_name = p_name+bifs+"-" if args.if_else or args.all_mut else p_name
    p_name = p_name+biops+"-" if args.incr_ops or args.all_mut else p_name
    p_name = p_name+str(dv)+"-" if args.dummy_var or args.all_mut else p_name
    p_name = p_name+block+"-" if args.reord_decls or args.all_mut else p_name
    p_name = p_name+fors+"-" if args.for_2_while or args.all_mut else p_name                                                     
    return p_name[:-1]
    
def instrument_file(input_file, output_dir):
    output_file, sincludes, includes = make_output_dir(input_file, output_dir)#, logfilename, loglibpath)
    try:
        ast = parse_file(output_file, use_cpp=True,
            cpp_path='gcc',
            cpp_args=['-E', '-Iutils/fake_libc_include'])
    except:
        return 0

    # print('******************** INPUT FILE: ********************')
    v = c_ast.NodeVisitor()
    v.visit(ast)
    # ast.show()
    # exit()
    # v = VariablesVisitor()
    v = MutatorVisitor()
    gen = c_generator.CGenerator ()
    n_ast = v.visit(ast)
    # n_ast.show()
    # return
    if args.verbose:
        print()
        print(input_file)
        print("Variables :", v.scope_vars)
        print("Number of BinOps of interest:", v.num_bin_ops_2_swap)
        print("Number of simple if-statements to swap", len(v.if_2_swap_ids))
        print("Number of increment operators to swap", len(v.inc_ops_2_swap_ids))
        print("Number of for-loops that can be translated into while-loops:", len(v.for_ids_2_swap))
        print("Declaration of variables:")
        print("  Number of blocks with vars declared:", len(v.blocks_vars))
        ord = 0
        for k in v.blocks_vars.keys():
            ord += len(v.blocks_vars[k]["permutations"])
        print("  Number of permutations:", ord)
    # return

    bin_ops_2_swap = gen_binary_lists(v.num_bin_ops_2_swap) if args.comp_ops or args.all_mut else gen_binary_lists(0)
    if_elses_2_swap = gen_binary_lists(len(v.if_2_swap_ids)) if args.if_else or args.all_mut else gen_binary_lists(0)
    inc_ops_2_swap = gen_binary_lists(len(v.inc_ops_2_swap_ids)) if args.incr_ops or args.all_mut else gen_binary_lists(0)
    dv_limit = -1 if args.dummy_var or args.all_mut else 0
    fors_2_swap = gen_binary_lists(len(v.for_ids_2_swap)) if args.for_2_while or args.all_mut else gen_binary_lists(0)
    block_permutations = get_possible_blocks_permutations(v.blocks_vars) if args.reord_decls or args.all_mut else [list()]
    n_reorderings = len(block_permutations)

    total_progs = len(bin_ops_2_swap)*len(if_elses_2_swap)*len(inc_ops_2_swap)*len(range(1, dv_limit, -1))*n_reorderings*len(fors_2_swap)
    if args.verbose:
        print("Number of possible reorderings: :", n_reorderings)
        print("\n#Total number of programs:", str(total_progs))
        
    if not args.enumerate_all or args.percentage_total_progs is not None:
        perc = 0.2
        if args.percentage_total_progs is not None:
            perc = float(args.percentage_total_progs)
        elif total_progs > 500:
            perc = 0.1 if total_progs < 100000 else 0.01

        min_per_mutation = 25
        bin_ops_2_swap = [bin_ops_2_swap[0]] + random.sample(bin_ops_2_swap[1:], max(int(perc * len(bin_ops_2_swap)-1), 1))
        if_elses_2_swap = [if_elses_2_swap[0]] + random.sample(if_elses_2_swap[1:], max(int(perc * len(if_elses_2_swap)-1), 1))
        inc_ops_2_swap = [inc_ops_2_swap[0]] + random.sample(inc_ops_2_swap[1:], max(int(perc * len(inc_ops_2_swap)-1), 1))
        fors_2_swap = [fors_2_swap[0]] + random.sample(fors_2_swap[1:], max(int(perc * len(fors_2_swap)-1), 1))
        block_permutations = [block_permutations[0]] + random.sample(block_permutations[1:], max(int(perc*len(block_permutations)), 1))
        n_reorderings = len(block_permutations)
        total_progs = len(bin_ops_2_swap)*len(if_elses_2_swap)*len(inc_ops_2_swap)*len(range(1, dv_limit, -1))*n_reorderings*len(fors_2_swap)
        perc = perc*0.9
        min_per_mutation = 1 if min_per_mutation == 1 else min_per_mutation - 1

        if args.verbose:
            print()
            print("Number of Programs with BinOps swapped:", len(bin_ops_2_swap))
            print("Number of Programs with if-statements swapped:", len(if_elses_2_swap))
            print("Number of Programs with swapped increment operators:", len(inc_ops_2_swap))
            print("Number of Programs with for translated 2 whiles loops:", len(fors_2_swap))
            print(" Number of blocks reorders:", n_reorderings)

        if args.verbose:
            print("\n\nNumber of possible reorderings (Sampled):", n_reorderings)
            total_progs = len(bin_ops_2_swap)*len(if_elses_2_swap)*len(inc_ops_2_swap)*len(range(1, dv_limit, -1))*n_reorderings*len(fors_2_swap)
            print("#Total number of programs (Sampled):", total_progs)
            print()

    total_progs = len(bin_ops_2_swap)*len(if_elses_2_swap)*len(inc_ops_2_swap)*len(range(1, dv_limit, -1))*n_reorderings*len(fors_2_swap)
    if args.info:
        #Total number of programs:"
        os.system("rm "+output_file)
        return total_progs
    # print(bin_numbers)
    var_maps = dict()
    prev_nums = list()
    for bops_n, bops_l in bin_ops_2_swap:
        # print(bops_n, bops_l)
        for bifs_n, bifs_l in if_elses_2_swap:
            for biops_n, biops_l in inc_ops_2_swap:
                for dummy_var in range(1, dv_limit, -1): # declaring new dummy variable
                    for b in range(n_reorderings):
                        for bfors_n, bfors_l in fors_2_swap:
                            block_bin =  binary_repr(b, width=len(binary_repr(n_reorderings)))
                            b_ast = parse_file(output_file, use_cpp=True, cpp_path='gcc', cpp_args=['-E', '-Iutils/fake_libc_include'])
                            prev_nums.append(get_prog_name(bops_n, bifs_n, biops_n, dummy_var, block_bin, bfors_n))
                            curr_num = prev_nums[-1]
                            if args.comp_ops or args.all_mut:
                                v_h = SwapBinOpsVisitor(list(bops_l))
                                b_ast = v_h.visit(b_ast)
                                var_maps[curr_num] = v.scope_vars
                                # if args.verbose:
                                #     print("SwapBinOpsVisitor done")
                            if args.if_else or args.all_mut:
                                v_h = SwapIfElseVisitor(list(bifs_l), v.if_2_swap_ids)
                                b_ast = v_h.visit(b_ast)
                                var_maps[curr_num] = v.scope_vars
                                # if args.verbose:
                                #     print("SwapIfElseVisitor done")
                            if args.incr_ops or args.all_mut:
                                v_h = SwapIncrDecrOpsVisitor(list(biops_l), v.inc_ops_2_swap_ids)
                                b_ast = v_h.visit(b_ast)
                                var_maps[curr_num] = v.scope_vars
                                # if args.verbose:
                                #     print("SwapIncrDecrOpsVisitor done")
                            if (args.reord_decls or args.all_mut) and block_permutations[b]!=[]:
                                # we need to verify if the program has no variables
                                v_h = ReorderVarDeclsVisitor(block_permutations[b])
                                b_ast = v_h.visit(b_ast)
                                var_maps[curr_num] = v.scope_vars
                                # if args.verbose:
                                #     print("ReorderVarDeclsVisitor done")
                            if args.for_2_while or args.all_mut:
                                v_h = For2WhileVisitor(list(bfors_l), v.for_ids_2_swap)
                                b_ast = v_h.visit(b_ast)
                                var_maps[curr_num] = v.scope_vars
                                # if args.verbose:
                                #     print("For2WhileVisitor done")
                            if args.dummy_var or args.all_mut:
                                v_h = DeclDumVarVisitor(v.scope_vars, True if dummy_var == 1 else False)
                                b_ast = v_h.visit(b_ast)
                                v2 = MutatorVisitor()
                                n_ast = v2.visit(b_ast)
                                var_maps[curr_num] = v2.scope_vars
                                # if args.verbose:
                                #     print("DeclDumVarVisitor done")

                            gen_output_file(gen, b_ast, sincludes + includes, curr_num, output_dir)
                            gen_variable_mappings(var_maps, curr_num, prev_nums, output_dir)
        
    os.system("rm "+output_file)
    
#-----------------------------------------------------------------

def gen_program_mutations(progs_dir, output_dir):
    total_progs = 0
    progs = list(pathlib.Path(progs_dir).glob('*.c'))
    for p in progs:
        np = str(p)
        if "/" in np:
            np = np.split("/")[-1]
        stu_id = np.split("-")[1] if "-" in np else np.replace(".c", "")
        if args.verbose:
            print("Dealing with student ", stu_id)
        try:
            s_muts = instrument_file(p, output_dir+"/"+stu_id)
        except:
            continue
        if args.info and s_muts is not None:
           total_progs += s_muts
    if args.info:
        print(total_progs)
        os.system("rm -rf "+output_dir)
        
    
#-----------------------------------------------------------------

def parser():
    parser = argparse.ArgumentParser(prog='prog_mutator.py', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-c', '--comp_ops', action='store_true', default=False, help='Swaps the comparison operators.')
    parser.add_argument('-if', '--if_else', action='store_true', default=False, help='Swaps the simple if-else-statements.')
    parser.add_argument('-io', '--incr_ops', action='store_true', default=False, help='Swaps the increment operators (e.g. i++, ++i and i+=1) if these are not used in a binary operation or in an assignment.')
    parser.add_argument('-dv', '--dummy_var', action='store_true', default=False, help='Declares a dummy variable in the beginning of the main function.')
    parser.add_argument('-rd', '--reord_decls', action='store_true', default=False, help='Reorder the order of variable declarations, when it is possible i.e., when two variables\' declarations do not depend on each other')
    parser.add_argument('-fw', '--for_2_while', action='store_true', default=False, help='Translates simple for-loops (without any continue instruction) into a while-loop.')
    parser.add_argument('-a', '--all_mut', action='store_true', default=False, help='Performs all the mutations above.')
    parser.add_argument('-p', '--percentage_total_progs', type=float, help='Instead of generating all possible mutations the script only generates this percentage. Default 0.01 if the total number of possible mutations is higher than 100k or 0.1 otherwise.')
    parser.add_argument('-d', '--input_dir', help='Name of the input directory.')
    parser.add_argument('-o', '--output_dir', help='Name of the output directory.')
    parser.add_argument('-info', '--info', action='store_true', default=False, help='Prints the total number of programs the required mutations can produced and exits without producing the sets of programs.')
    parser.add_argument('-ea', '--enumerate_all', action='store_true', default=False, help='Enumerates all possible mutated programs. NOTE: Sometimes the number of mutated programs is more than 200K Millions of programs.')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Prints debugging information.')
    args = parser.parse_args(argv[1:])
    return args


if __name__ == "__main__":
    args = parser()
    if len(sys.argv) >= 2:
        input_dir = args.input_dir
        output_dir = args.output_dir
        gen_program_mutations(input_dir, output_dir)
    else:
        print('{0} -h'.format(sys.argv[0]))
         

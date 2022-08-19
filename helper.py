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
import random
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

    # output_file = output_dir + '/' + os.path.basename(input_file)
    output_file = output_dir + '/tmp_input_file.c'
    with open(output_file, 'w') as writer:
        writer.writelines(sincludes)
        writer.writelines(includes)
        writer.write('void fakestart() {;}\n')
        writer.writelines(noincludes)

    return output_file, sincludes, includes

def get_output_file_name(filename, output_dir):
    return output_dir + '/' + filename + ".c"
    
def gen_output_file(c_gen, ast, includes, filename, output_dir):
    output_file = get_output_file_name(filename, output_dir)
    str_ast = c_gen.visit(ast)
    # print(str_ast)
    # str_ast = remove_fakestart(str_ast)
    with open(output_file, 'w') as writer:
        writer.writelines(includes)
        writer.write(str_ast)

def write_program(ast, c_gen, output_file, includes):
    # write a clean program without any fakestart info
    cu = CleanUpVisitor()
    ast_cleaned = cu.visit(ast)
    str_ast = c_gen.visit(ast_cleaned)
    # print(str_ast)
    with open(output_file, 'w') as writer:
        writer.writelines(includes)
        writer.write(str_ast)

def program_checker(ast, c_gen, includes, ipa):
    tmp_file = "/tmp/tmp-{n}.c".format(n=int(random.random()*100000000))
    write_program(ast, c_gen, tmp_file, includes)
    # print(tmp_file)
    return check_program(tmp_file, ipa)

def check_program(tmp_file, ipa):
    os.system("./prog_checker.sh {p} {lab} > {o}".format(p=tmp_file, lab=ipa, o=tmp_file[:-2]+".o")) 
    with open(tmp_file[:-2]+".o", 'r') as f:
        lines = f.readlines()
        # print(lines)
        if "WRONG\n" in lines:
            return False
        return True

#-----------------------------------------------------------------
# A visitor that removes the fakestart
class CleanUpVisitor(c_ast.NodeVisitor):
    def __init__ (self):
        super().__init__()
        
    def visit_FileAST(self, node):
        #print('****************** Found FileAST Node *******************')
        n_ext = []
        fakestart_pos = -1 #for the case of our injected function which do not have the fakestart function in their ast
        for e in range(len(node.ext)):
            x = node.ext[e]
            if fakestart_pos==-1 and isinstance(x, c_ast.FuncDef) and "fakestart" in x.decl.type.type.declname:
                fakestart_pos=e
        
        n_file_ast = c_ast.FileAST(node.ext[fakestart_pos+1:])
        return n_file_ast

    
#-----------------------------------------------------------------
# A generic visitor that visits the entire AST (at least that's the idea :') )
class ASTVisitor(c_ast.NodeVisitor):

    def __init__ (self):
        super().__init__()
        self.pn = None # parent node 
                        
    _method_cache = None

    def visit(self, node):
        """ Visit a node.
        """

        if self._method_cache is None:
            self._method_cache = {}

        visitor = self._method_cache.get(node.__class__.__name__, None)
        if visitor is None:
            method = 'visit_' + node.__class__.__name__
            visitor = getattr(self, method, self.generic_visit)
            self._method_cache[node.__class__.__name__] = visitor

        return visitor(node)

    def get_node_name(self, node):
        return node.__class__.__name__
    
    def visit_FileAST(self, node):
        #print('****************** Found FileAST Node with Parent Node ****************')
        n_ext = []
        fakestart_pos = -1 #for the case of our injected function which do not have the fakestart function in their ast
        prv_pn = self.pn
        self.pn = self.get_node_name(node)        
        for e in range(len(node.ext)):
            x = node.ext[e]
            # n_ext.append(self.visit(x, node_id(x.coord)))
            if isinstance(x, c_ast.FuncDef) and "fakestart" in x.decl.type.type.declname:
                fakestart_pos=e


        fakestart_pos = -1        
        for e in range(fakestart_pos+1, len(node.ext)):
            x = node.ext[e]
            n_ext.append(self.visit(x))

        self.pn = prv_pn
        n_file_ast = c_ast.FileAST(n_ext)
        return n_file_ast

    def visit_Decl(self, node):
        #print('****************** Found Decl Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        if not isinstance(node.type, c_ast.TypeDecl) and not isinstance(node.type, c_ast.ArrayDecl):
            if node.init is not None:
                node.init = self.visit(node.init)

            # because it can be other type of declaration. Like func declarations.
            node.type = self.visit(node.type)
            self.pn = prv_pn
            return node

        if node.init is not None:
            node.init = self.visit(node.init)

        self.pn = prv_pn    
        return node

    def visit_TypeDecl(self, node):
        #print('****************** Found Type Decl Node with Parent Node '+self.pn+'****************')
        # attrs: declname, quals, align, type
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        self.type = self.visit(node.type)
        self.pn = prv_pn 
        return node
    
    def visit_ArrayDecl(self, node):
        #print('****************** Found Array Decl Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        if node.dim is not None:
            node.dim = self.visit(node.dim)
        self.pn = prv_pn 
        return node

    def visit_PtrDecl(self, node):
        #print('****************** Found Pointer Decl Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        node.type = self.visit(node.type)
        self.pn = prv_pn
        return node

    def visit_ArrayRef(self, node):
        #print('****************** Found Array Ref Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        node.name = self.visit(node.name)
        node.subscript = self.visit(node.subscript)
        self.pn = prv_pn
        return node

    def visit_Assignment(self, node):
        #print('****************** Found Assignment Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        node.rvalue = self.visit(node.rvalue)
        node.lvalue = self.visit(node.lvalue)
        self.pn = prv_pn
        return node

    def visit_ID(self, node):
        #print('****************** Found ID Node with Parent Node '+self.pn+'****************')
        return node

    def visit_Constant(self, node):
        #print('****************** Found Constant Node with Parent Node '+self.pn+'****************')
        return node
    
    def visit_ExprList(self, node):
        #print('****************** Found ExprList Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        for e in node.exprs:
            e = self.visit(e)
        self.pn = prv_pn
        return node

    def visit_ParamList(self, node):
        #print('****************** Found ParamList Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        for e in node.params:
            e = self.visit(e)
        self.pn = prv_pn
        return node
    
    def visit_Cast(self, node):
        #print('******************** Found Cast Node with Parent Node '+self.pn+'******************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        node.expr = self.visit(node.expr)
        self.pn = prv_pn
        return node

    def visit_UnaryOp(self, node):
        #print('****************** Found Unary Operation with Parent Node '+self.pn+'*******************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        node.expr = self.visit(node.expr)
        self.pn = prv_pn
        return node

    def visit_BinaryOp(self, node):
        #print('****************** Found Binary Operation with Parent Node '+self.pn+'*******************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        left = self.visit(node.left)
        right = self.visit(node.right)
        self.pn = prv_pn
        return c_ast.BinaryOp(node.op, left, right, node.coord)

    def visit_TernaryOp(self, node):
        #print('****************** Found TernaryOp Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        n_cond = self.visit(node.cond)
        if isinstance(node.iftrue, c_ast.Compound):
            n_iftrue = self.visit(node.iftrue)
        else:
            n_iftrue = self.visit(c_ast.Compound([node.iftrue], node.iftrue.coord))
        
        n_iffalse = node.iffalse
        if node.iffalse is not None:
            if not isinstance(node.iffalse, c_ast.Compound):
                node.iffalse = c_ast.Compound([node.iffalse], node.iffalse.coord)
            node.iffalse = self.visit(node.iffalse)
        
        #print('****************** New Cond Node with Parent Node '+self.pn+'****************')
        n_ternary = c_ast.TernaryOp(n_cond, n_iftrue, n_iffalse, node.coord)
        self.pn = prv_pn
        return n_ternary

    def visit_FuncDecl(self, node):
        #print('****************** Found FuncDecl Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        if node.args:
            node.args = self.visit(node.args)
        self.pn = prv_pn
        return node

    def visit_FuncDef(self, node):
        #print('****************** Found FuncDef Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        decl = node.decl
        param_decls = node.param_decls
        if node.param_decls:
            param_decls = self.visit(node.param_decls)
        if "main" != node.decl.name and "fakestart" != node.decl.name: #ignore main function
            # if the function has parameters add them to the scope
            if decl.type.args:
                decl.type.args = self.visit(decl.type.args)
                
        body = node.body
        coord = node.coord
        n_body_1 = self.visit(body)
        n_func_def_ast = c_ast.FuncDef(decl, param_decls, n_body_1, coord)
        self.pn = prv_pn
        return n_func_def_ast

    def visit_FuncCall(self, node):
        #print('****************** Found FuncCall Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        if node.args:
            node.args = self.visit(node.args)
        self.pn = prv_pn
        return node
    
    def visit_Compound(self, node):
        #print('****************** Found Compound Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        block_items = node.block_items
        coord = node.coord
        n_block_items = []
        if block_items is not None:
            for x in block_items:
                n_block_items.append(self.visit(x))

        n_compound_ast = c_ast.Compound(n_block_items, coord)
        self.pn = prv_pn
        return n_compound_ast

    def visit_If(self, node):
        #print('****************** Found IF Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        n_cond = self.visit(node.cond)
        if isinstance(node.iftrue, c_ast.Compound):
            n_iftrue = self.visit(node.iftrue)
        else:
            n_iftrue = self.visit(c_ast.Compound([node.iftrue], node.iftrue.coord))

        n_iffalse = node.iffalse
        if node.iffalse is not None:
            if not isinstance(node.iffalse, c_ast.Compound):
                node.iffalse = c_ast.Compound([node.iffalse], node.iffalse.coord)
            node.iffalse = self.visit(node.iffalse)
        #print('****************** New Cond Node with Parent Node '+self.pn+'****************')
        n_if = c_ast.If(n_cond, n_iftrue, n_iffalse, node.coord)
        self.pn = prv_pn
        return n_if

    def visit_For(self, node):
        #print('****************** Found For Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        n_init = self.visit(node.init)
        n_cond = self.visit(node.cond)
        if isinstance(node.stmt, c_ast.Compound):
            n_stmt = self.visit(node.stmt)
        else:
            n_stmt = self.visit(c_ast.Compound([node.stmt], node.stmt.coord))
        n_next = node.next
        if n_next is not None:
            n_next = self.visit(node.next)

        n_for = c_ast.For(n_init, n_cond, n_next, n_stmt, node.coord)
        self.pn = prv_pn
        return n_for

    def visit_While(self, node):
        #print('****************** Found While Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        n_cond = self.visit(node.cond)
        if isinstance(node.stmt, c_ast.Compound):
            n_stmt = self.visit(node.stmt)
        else:
            n_stmt = self.visit(c_ast.Compound([node.stmt], node.stmt.coord))
        n_while = c_ast.While(n_cond, n_stmt, node.coord)
        self.pn = prv_pn
        return n_while

    def visit_DoWhile(self, node):
        #print('****************** Found DoWhile Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        n_cond = self.visit(node.cond)
        if isinstance(node.stmt, c_ast.Compound):
            n_stmt = self.visit(node.stmt)
        else:
            n_stmt = self.visit(c_ast.Compound([node.stmt], node.stmt.coord))
        n_dowhile = c_ast.DoWhile(n_cond, n_stmt, node.coord)
        self.pn = prv_pn
        return n_dowhile

    def visit_Switch(self, node):
        #print('****************** Found Switch Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        n_cond = self.visit(node.cond)
        if isinstance(node.stmt, c_ast.Compound):
            n_stmt = self.visit(node.stmt)
        else:
            n_stmt = self.visit(c_ast.Compound([node.stmt], node.stmt.coord))
        n_switch = c_ast.Switch(n_cond, n_stmt, node.coord)
        self.pn = prv_pn
        return n_switch

    def visit_Return(self, node):
        #print('****************** Found Return Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        if node.expr:
            node.expr = self.visit(node.expr)
        self.pn = prv_pn
        return node

    def visit_Break(self, node):
        #print('****************** Found Break Node with Parent Node '+self.pn+'****************')
        return node

    def visit_Continue(self, node):
        #print('****************** Found Continue Node with Parent Node '+self.pn+'****************')
        return node

    def visit_Case(self, node):
        #print('****************** Found Case Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        n_stmts_1 = []
        for x in node.stmts:
            n_stmts_1.append(self.visit(x))
            
        n_stmts_2 = c_ast.Compound (n_stmts_1, node.coord)
        self.pn = prv_pn
        return c_ast.Case(node.expr, n_stmts_2, node.coord)

    def visit_Default(self, node):
        #print('****************** Found Default Node with Parent Node '+self.pn+'****************')
        prv_pn = self.pn
        self.pn = self.get_node_name(node)
        n_stmts_1 = []
        for x in node.stmts:
            n_stmts_1.append(self.visit(x))
            
        n_stmts_2 = c_ast.Compound(n_stmts_1, node.coord)
        self.pn = prv_pn
        return c_ast.Default(n_stmts_2, node.coord)

    def visit_EmptyStatement(self, node):
        #print('****************** Found EmptyStatement Node with Parent Node '+self.pn+'****************')
        return node

    def generic_visit(self, node):
        #print('******************  Something else ************')
        return node
    
        
if __name__ == '__main__':
    pass

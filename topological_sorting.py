#!/usr/bin/python
#Title			: topological_sorting.py
#Usage			: python topological_sorting.py
#Author			: pmorvalho
#Date			: May 17, 2022
#Description 	        : Computes all the topological ordering from a set of nodes and their respective edges.
#Notes			: Code adapted from https://www.techiedelight.com/find-all-possible-topological-orderings-of-dag/
#Python Version: 3.8.5
# (C) Copyright 2022 Pedro Orvalho.
#==============================================================================

import argparse
from sys import argv

class Graph:
 
    def __init__(self, edges, nodes):
 
        # A list of lists to represent an adjacency list
        self.paths = []
        self.nodes = nodes
        self.adjList = dict()
        for n in nodes:
            self.adjList[n] = [] 
 
        # stores in-degree of a vertex
        # initialize in-degree of each vertex by 0
        self.indegree = dict()

        for n in nodes:
            self.indegree[n] = 0
        # add edges to the directed graph
        for (src, dest) in edges:
 
            # add an edge from source to destination
            self.adjList[src].append(dest)
 
            # increment in-degree of destination vertex by 1
            self.indegree[dest] = self.indegree[dest] + 1
 
# Recursive function to find all topological orderings of a given DAG
def findAllTopologicalOrderings(graph, path, discovered, nodes):
    # do for every vertex
    for v in nodes:
 
        # proceed only if the current node's in-degree is 0 and
        # the current node is not processed yet
        if graph.indegree[v] == 0 and not discovered[v]:
 
            # for every adjacent vertex `u` of `v`, reduce the in-degree of `u` by 1
            for u in graph.adjList[v]:
                graph.indegree[u] = graph.indegree[u] - 1
 
            # include the current node in the path and mark it as discovered
            path.append(v)
            discovered[v] = True
 
            # recur
            findAllTopologicalOrderings(graph, list(path), discovered, nodes)
 
            # backtrack: reset in-degree information for the current node
            for u in graph.adjList[v]:
                graph.indegree[u] = graph.indegree[u] + 1
 
            # backtrack: remove the current node from the path and
            # mark it as undiscovered
            path.pop()
            discovered[v] = False
 
    # print the topological order if all vertices are included in the path
    if len(path) == len(nodes):
        graph.paths.append(list(path))
 
 
# Print all topological orderings of a given DAG
def getTopologicalOrders(nodes, edges):

    graph = Graph(edges, nodes) 
    discovered = dict()
    for n in nodes:
        discovered[n] = False
 
    # list to store the topological order
    path = []
    # find all topological ordering and print
    findAllTopologicalOrderings(graph, path, discovered, nodes)
    return graph.paths
    
 
if __name__ == '__main__':
    # int a = 0;
    # int b = a;
    # int c = 2;
    # List of graph edges as per the above diagram
    edges = [(41, 44)] 
    # total number of nodes in the graph (labelled from 0 to 7)
    n = [40, 41, 44, 39]
 
    # print all topological ordering of the graph
    print(getTopologicalOrders(n, edges))

#!/usr/bin/env python

# Yet another MGC compiler
# Author Adam Bobowski
#
# Compiler runner

import argparse

from lib.errors import YamcError
from lib.parser import Parser
from lib.static_analysis import CodeAnalysis
from lib.flow_graph import FlowGraph
from lib.machine_code import MachineCode


def main():
    args = parse_args()
    compilation(args.file_path, args.out)


def parse_args():
    parser = argparse.ArgumentParser(description='Compile with Yamc.')
    parser.add_argument(
        'file_path',
        help='.imp file'
        )
    parser.add_argument(
        '--out',
        default="a.mr",
        help='place the output into OUT')
    return parser.parse_args()


def compilation(file_path, out_path):
    parser = Parser()
    analyser = CodeAnalysis()
    flow_graph = FlowGraph()
    machine_code = MachineCode()

    with open(file_path, 'r') as f:
        content = f.read()

    try:
        ptree = parser.parse(content)
        symtab, ast = analyser.check(ptree)
        graph = flow_graph.convert(ast)
        code = machine_code.gen(graph, symtab)
    except YamcError:
        exit(1)

    with open(out_path, 'w') as f:
        for line in code:
            f.write(line + '\n')


if __name__ == '__main__':
    main()

# Author Adam Bobowski
#
# Static semantic analysis

import logging

from itertools import chain

from errors import YamcError


class CodeAnalysis(object):
    def __init__(self):
        self.glob = None   # global variables
        self.init = None   # initilized variables
        self.iter_no = 0

    def check(self, ptree):
        _, declarations, commands = ptree

        # static analysis
        self.check_double_declaration(declarations)
        self.check_undeclared(declarations, commands)

        # if succeeded create ast and symtab
        ast = self.create_ast(commands)
        symtab = self.create_symtab(declarations)
        return symtab, ast

    def check_double_declaration(self, declarations):
        seen = []
        doubles = []

        for d in declarations:
            if d[1] not in seen:
                seen.append(d[1])
            else:
                doubles.append(d)

        if doubles:
            for d in doubles:
                logging.error('In line %d', d[-1])
                logging.error('Double declaraton of "%s"', d[1])
            raise YamcError()

    def check_undeclared(self, declarations, commands):
        self.glob = set([a[:2] for a in declarations])
        self.init = set()
        local = set()

        self.check_commands(commands, local)

    def check_commands(self, cmds, local):
        if not cmds:
            return
        for i in cmds:
            getattr(self, 'check_' + i[0])(i, local)

    def check_value(self, value, local, is_r_value=True):
        if isinstance(value, long):
            return

        if value[0] == 'int[]':  # Check index
            self.check_value(value[2], local)

        v = value[:2]  # get (type, name) only
        if not (v in self.glob or v in local):
            logging.error('In line %d', value[-1])
            logging.error('Undeclared variable "%s %s"', value[0], value[1])
            raise YamcError()

        if is_r_value and v not in self.init and v[0] == 'int':
            logging.error('In line %d', value[-1])
            logging.error('Uninitialized variable "%s %s"', value[0], value[1])
            raise YamcError()
        else:
            self.init.add(v)

    def check_op(self, op, local):
        if len(op) == 2:
            self.check_value(op[1], local)
        else:
            self.check_value(op[2], local)
            self.check_value(op[3], local)

    def check_assign(self, assign, local):
        if assign[1][:2] in local:
            logging.error('In line %d', assign[1][-1])
            logging.error('Assignment to iterator "%s"', assign[1][1])
            raise YamcError()
        self.check_op(assign[2], local)
        self.check_value(assign[1], local, is_r_value=False)

    def check_if_then(self, cmd, local):
        _, condition, commands = cmd
        self.check_op(condition, local)
        self.check_commands(commands, local)

    def check_if_else(self, cmd, local):
        _, condition, if_cmds, else_cmds = cmd
        self.check_op(condition, local)
        self.check_commands(if_cmds, local)
        self.check_commands(else_cmds, local)

    def check_while(self, cmd, local):
        _, condition, commands = cmd
        self.check_op(condition, local)
        self.check_commands(commands, local)

    def check_for_up(self, cmd, local):
        _, iterator, begin, end, commands = cmd
        self.check_value(begin, local)
        self.check_value(end, local)
        local = self.add_iterator(iterator, local)
        self.check_commands(commands, local)

    def check_for_down(self, cmd, local):
        self.check_for_up(cmd, local)

    def add_iterator(self, iterator, local):
        iterator = iterator[:2]
        local = set(local)
        local.add(iterator)
        self.init.add(iterator)
        return local

    def check_get(self, cmd, local):
        _, variable = cmd
        self.check_value(variable, local, is_r_value=False)

    def check_put(self, cmd, local):
        _, variable = cmd
        self.check_value(variable, local)

    def create_ast(self, commands):
        return self.ast_commands(commands, {})

    def ast_commands(self, cmds, it_rep):
        if not cmds:
            return []
        return [getattr(self, "ast_" + i[0])(i, it_rep) for i in cmds]

    # resolve iterator to unique name
    def ast_value(self, value, it_rep):
        if isinstance(value, long):
            return value

        if len(value) - 1 == 3:
            a = it_rep.get(value[1], value[1])
            b = self.ast_value(value[2], it_rep)
            return a, b
        else:
            return it_rep.get(value[1], value[1])

    # Constant expression optimization
    def ast_expression(self, expr, it_rep):
        if len(expr) == 2:
            return self.ast_value(expr[1], it_rep)

        _, operation, l, r = expr
        l = self.ast_value(l, it_rep)
        r = self.ast_value(r, it_rep)

        if isinstance(l, long) and isinstance(r, long):
            ops = {
                '+': lambda l, r: l + r,
                '-': lambda l, r: max(l - r, 0),
                '*': lambda l, r: l * r,
                '/': lambda l, r: l / r,
                '%': lambda l, r: l % r
            }
            return ops[operation](l, r)
        return (expr[1], l, r)

    def ast_condition(self, cmd, it_rep):
        _, condition, l, r = cmd
        l = self.ast_value(l, it_rep)
        r = self.ast_value(r, it_rep)
        return (condition, l, r)

    def ast_assign(self, cmd, it_rep):
        _, l, r = cmd
        l = self.ast_value(l, it_rep)
        r = self.ast_expression(r, it_rep)
        return ('assign', l, r)

    def ast_if_then(self, cmd, it_rep):
        _, condition, commands = cmd
        condition = self.ast_condition(condition, it_rep)
        commands = self.ast_commands(commands, it_rep)
        return ('if_then', condition, commands)

    def ast_if_else(self, cmd, it_rep):
        _, condition, if_cmds, else_cmds = cmd
        condition = self.ast_condition(condition, it_rep)
        if_cmds = self.ast_commands(if_cmds, it_rep)
        else_cmds = self.ast_commands(else_cmds, it_rep)
        return ('if_else', condition, if_cmds, else_cmds)

    def ast_while(self, cmd, it_rep):
        _, condition, commands = cmd
        condition = self.ast_condition(condition, it_rep)
        commands = self.ast_commands(commands, it_rep)
        return ('while', condition, commands)

    def ast_for_up(self, cmd, it_rep):
        loop, iterator, begin, end, commands = cmd
        it_rep = dict(it_rep)
        it_rep[iterator[1]] = '@' + str(self.iter_no)
        self.iter_no += 1

        iterator = self.ast_value(iterator, it_rep)
        begin = self.ast_value(begin, it_rep)
        end = self.ast_value(end, it_rep)
        commands = self.ast_commands(commands, it_rep)
        return (loop, iterator, begin, end, commands)

    def ast_for_down(self, cmd, it_rep):
        return self.ast_for_up(cmd, it_rep)

    def ast_get(self, cmd, it_rep):
        _, variable = cmd
        return ('get', self.ast_value(variable, it_rep))

    def ast_put(self, cmd, it_rep):
        _, variable = cmd
        return ('put', self.ast_value(variable, it_rep))

    def create_symtab(self, declarations):
        symtab = [t[:len(t)-1] for t in declarations]
        tables = [t[1:] for t in symtab if t[0] == 'int[]']
        integers = [t[1] for t in symtab if t[0] == 'int']
        def f(x): return '@' + str(x)
        def g(x): return '#' + str(x)
        helpers = list(chain.from_iterable((f(x), g(x))
                       for x in xrange(self.iter_no)))
        integers.extend(helpers)

        k = 0
        symtab = {}
        for name in integers:
            symtab[name] = k
            k += 1
        for name, size in tables:
            symtab[name] = k
            k += size

        return symtab

# Author Adam Bobowski
#
# Parse tree to Control Flow Graph conversion


class FlowGraph(object):
    def __init__(self):
        self.cfg = None

    def convert(self, ast):
        self.cfg = []

        self.cfg_commands(ast)
        self.cfg[-1].append(('halt',))
        return self.cfg

    def cfg_commands(self, cmds):
        self.cfg.append([])
        for i in cmds:
            getattr(self, "cfg_" + i[0])(i)

    def cfg_assign(self, cmd):
        self.cfg[-1].append(cmd)

    def cfg_get(self, cmd):
        self.cfg[-1].append(cmd)

    def cfg_put(self, cmd):
        self.cfg[-1].append(cmd)

    def cfg_if_then(self, cmd):
        _, condition, commands = cmd
        index = len(self.cfg) - 1

        self.cfg_commands(commands)
        self.cfg.append([])

        condition = self.cfg_negate_condition(condition)
        self.cfg[index].append(('if', condition, len(self.cfg) - 1))

    def cfg_if_else(self, cmd):
        _, condition, if_cmds, else_cmds = cmd
        if_index = len(self.cfg) - 1

        self.cfg_commands(if_cmds)
        goto_index = len(self.cfg) - 1
        self.cfg_commands(else_cmds)
        self.cfg.append([])

        condition = self.cfg_negate_condition(condition)
        self.cfg[if_index].append(('if', condition, goto_index + 1))
        self.cfg[goto_index].append(('goto', len(self.cfg) - 1))

    def cfg_while(self, cmd):
        _, condition, commands = cmd
        self.cfg.append([])
        index = len(self.cfg) - 1

        self.cfg_commands(commands)
        self.cfg[-1].append(('goto', index))
        self.cfg.append([])

        condition = self.cfg_negate_condition(condition)
        self.cfg[index].append(('if', condition, len(self.cfg) - 1))

    def cfg_for_up(self, cmd):
        _, iterator, begin, end, commands = cmd
        counter = '#' + iterator[1:]

        self.cfg[-1].extend([
            ('assign', iterator, begin),
            ('assign', counter, end + 1 if isinstance(end, long) else ('+', end, long(1))),
            ('assign', counter, ('-', counter, iterator)),
        ])

        self.cfg.append([])
        index = len(self.cfg) - 1

        self.cfg_commands(commands)
        self.cfg[-1].extend([
            ('assign', iterator, ('+', iterator, long(1))),
            ('assign', counter, ('-', counter, long(1))),
            ('goto', index)
        ])
        self.cfg.append([])

        self.cfg[index].append(('if', ('=', counter, long(0)), len(self.cfg) - 1))

    def cfg_for_down(self, cmd):
        _, iterator, begin, end, commands = cmd
        counter = '#' + iterator[1:]

        self.cfg[-1].extend([
            ('assign', iterator, begin),
            ('assign', counter, ('+', iterator, long(1))),
            ('assign', counter, ('-', counter, end)),
        ])

        self.cfg.append([])
        index = len(self.cfg) - 1

        self.cfg_commands(commands)
        self.cfg[-1].extend([
            ('assign', iterator, ('-', iterator, long(1))),
            ('assign', counter, ('-', counter, long(1))),
            ('goto', index)
        ])
        self.cfg.append([])

        self.cfg[index].append(('if', ('=', counter, long(0)), len(self.cfg) - 1))

    def cfg_negate_condition(self, cond):
        negation = {
            '=': '!=',
            '!=': '=',
            '<': '>=',
            '>': '<=',
            '<=': '>',
            '>=': '<'
        }
        return (negation[cond[0]],) + cond[1:]

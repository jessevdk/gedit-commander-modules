import commander.commands as commands
import commander.commands.completion
import commander.commands.result
import commander.commands.exceptions

import re

__commander_module__ = True

class ParamSpec:
    def __init__(self, name, nick, desc, flags):
        self.name = name
        self.nick = nick
        self.desc = desc
        self.flags = flags

        self.args = []

    def prop_enum(self):
        return 'PROP_' + self.name.upper().replace('-', '_')

    def read(self):
        pass

    def spec_name(self):
        name = self.__class__.__name__

        if name.startswith('ParamSpec'):
            name = name[len('ParamSpec'):]

        return name.lower()

    def format_str(self, s):
        if s.startswith('"') or s.startswith('_("'):
            return s

        return '"%s"' % (s.replace('"', '\\"'),)

    def __str__(self):
        name = "g_param_spec_" + self.spec_name()
        indent = " " * (len(name) + 2)

        argstr = ''

        if self.args:
            ret = (",\n%s" % (indent,)).join(map(lambda x: str(x), self.args))
            argstr = "\n%s%s," % (indent, ret)

        return "%s (%s,\n%s%s,\n%s%s,%s\n%s%s)" % (name,
                                                 self.format_str(self.name),
                                                 indent,
                                                 self.format_str(self.nick),
                                                 indent,
                                                 self.format_str(self.desc),
                                                 argstr,
                                                 indent,
                                                 self.flags)

    def write(self):
        delim = "\n" + (" " * 33)
        spec = delim.join(str(self).splitlines())

        return """
g_object_class_install_property (object_class,
                                 %s,
                                 %s);""" % (self.prop_enum(), spec)

class ParamSpecTyped(ParamSpec):
    def __init__(self, name, nick, desc, flags):
        ParamSpec.__init__(self, name, nick, desc, flags)

    def read(self):
        typ, words, modifier = (yield commander.commands.result.Prompt('Type:'))
        self.args.append(typ)

        yield True

class ParamSpecBoolean(ParamSpec):
    def __init__(self, name, nick, desc, flags):
        ParamSpec.__init__(self, name, nick, desc, flags)

    def read(self):
        comp = {'*': commander.commands.completion.words(['TRUE', 'FALSE'])}

        default, words, modifier = (yield commander.commands.result.Prompt('Default value [TRUE]:', comp))

        if default.lower() != 'false':
            self.args = ['TRUE']
        else:
            self.args = ['FALSE']

        yield True

class ParamSpecBoxed(ParamSpecTyped):
    def __init__(self, name, nick, desc, flags):
        ParamSpecTyped.__init__(self, name, nick, desc, flags)

class ParamSpecNumeric(ParamSpec):
    def __init__(self, name, nick, desc, flags):
        ParamSpec.__init__(self, name, nick, desc, flags)

    def min_value(self):
        return '0'

    def max_value(self):
        return '0'

    def default_value(self):
        return '0'

    def read(self):
        minv, words, modifier = (yield commander.commands.result.Prompt('Min [' + self.min_value() + ']:'))
        maxv, words, modifier = (yield commander.commands.result.Prompt('Max [' + self.max_value() + ']:'))
        default, words, modifier = (yield commander.commands.result.Prompt('Default [' + self.default_value() + ']:'))

        if not minv:
            minv = self.min_value()

        if not maxv:
            maxv = self.max_value()

        if not default:
            default = self.default_value()

        self.args = [minv, maxv, default]

        yield True

class ParamSpecDouble(ParamSpecNumeric):
    def __init__(self, name, nick, desc, flags):
        ParamSpecNumeric.__init__(self, name, nick, desc, flags)

    def min_value(self):
        return 'G_MINDOUBLE'

    def max_value(self):
        return 'G_MAXDOUBLE'

class ParamSpecEnum(ParamSpecTyped):
    def __init__(self, name, nick, desc, flags):
        ParamSpec.__init__(self, name, nick, desc, flags)

    def read(self):
        yield ParamSpecTyped.read(self)

        default, words, modifier = (yield commander.commands.result.Prompt('Default: [0]'))

        if default == '':
            default = '0'

        self.args.append(default)

        yield True

class ParamSpecFlags(ParamSpecEnum):
    def __init__(self, name, nick, desc, flags):
        ParamSpecEnum.__init__(self, name, nick, desc, flags)

class ParamSpecFloat(ParamSpecNumeric):
    def __init__(self, name, nick, desc, flags):
        ParamSpecNumeric.__init__(self, name, nick, desc, flags)

    def min_value(self):
        return 'G_MINFLOAT'

    def max_value(self):
        return 'G_MAXFLOAT'

class ParamSpecInt(ParamSpecNumeric):
    def __init__(self, name, nick, desc, flags):
        ParamSpecNumeric.__init__(self, name, nick, desc, flags)

    def min_value(self):
        return 'G_MININT'

    def max_value(self):
        return 'G_MAXINT'

class ParamSpecUInt(ParamSpecNumeric):
    def __init__(self, name, nick, desc, flags):
        ParamSpecNumeric.__init__(self, name, nick, desc, flags)

    def min_value(self):
        return '0'

    def max_value(self):
        return 'G_MAXUINT'

class ParamSpecObject(ParamSpecTyped):
    def __init__(self, name, nick, desc, flags):
        ParamSpecTyped.__init__(self, name, nick, desc, flags)

class ParamSpecPointer(ParamSpec):
    def __init__(self, name, nick, desc, flags):
        ParamSpec.__init__(self, name, nick, desc, flags)

class ParamSpecString(ParamSpec):
    def __init__(self, name, nick, desc, flags):
        ParamSpec.__init__(self, name, nick, desc, flags)

    def read(self):
        default, words, modifier = (yield commander.commands.result.Prompt('Default [NULL]:'))

        if not default:
            default = 'NULL'

        if not default.startswith('"') and not default.startswith('_("') and default != 'NULL':
            default = '"' + default.replace('"', '\\"') + '"'

        self.args.append(default)

        yield True

_prop_types = {
    'boolean': ParamSpecBoolean,
    'boxed': ParamSpecBoxed,
    'double': ParamSpecDouble,
    'enum': ParamSpecEnum,
    'flags': ParamSpecFlags,
    'float': ParamSpecFloat,
    'int': ParamSpecInt,
    'object': ParamSpecObject,
    'pointer': ParamSpecPointer,
    'string': ParamSpecString,
    'uint': ParamSpecUInt
}

def __default__(view, entry):
    """GObject utilities

Utility functions for GObject C files."""
    pass

def _find_regex_per_line(buf, regex, start=None):
    if not start:
        start = buf.get_start_iter()

    if isinstance(regex, str) or isinstance(regex, unicode):
        regex = re.compile(regex)

    while True:
        end = start.copy()

        if not end.ends_line():
            end.forward_to_line_end()

        text = start.get_text(end)

        m = regex.search(text)

        if m:
            end = start.copy()
            start.forward_chars(m.start(0))
            end.forward_chars(m.end(0))

            return [start, end, m]

        if not start.forward_line():
            break

    return None

def _find_regex(buf, regex, start=None):
    if not start:
        start = buf.get_start_iter()

    end = buf.get_end_iter()
    text = start.get_text(end)

    if isinstance(regex, str) or isinstance(regex, unicode):
        regex = re.compile(regex)

    m = regex.search(text)

    if m:
        end = start.copy()
        start.forward_chars(m.start(0))
        end.forward_chars(m.end(0))

        return [start, end, m]

    return None

def _find_prop_enum(buf):
    ret = _find_regex_per_line(buf, '^\s*PROP_0\\s*,')

    if ret:
        ret = _find_regex_per_line(buf, '^};$', ret[1])

        if not ret:
            return None

        ret[0].backward_char()
        return ret[0]
    else:
        ret = _find_regex_per_line(buf, '^\s*G_DEFINE_(DYNAMIC_|ABSTRACT_)?TYPE')

        if not ret:
            return None

        ret = _find_regex_per_line(buf, '^$', ret[1])

        if not ret:
            return None

        start = ret[0]
        buf.insert(start, "\nenum\n{\n\tPROP_0\n};\n")
        start.backward_chars(4)

        return start

def _get_type_name(buf):
    ret = _find_regex_per_line(buf, '^\s*G_DEFINE_(?:DYNAMIC_|ABSTRACT_)?TYPE[^(]*\\(\s*([A-Za-z_0-9]+)')

    if ret:
        camel = ret[2].group(1)
        parts = re.findall('[A-Z]+[a-z0-9]*', camel)

        return camel, parts

def _find_class_init(buf, namespec):
    funcprefix = '_'.join(namespec[1]).lower()

    ret = _find_regex(buf, 'static\s+void\s+%s_class_init\s*\\(' % (funcprefix, ))

    if not ret:
        return None

    return ret[0]

def _find_prop_get_set(buf, namespec, isget):
    funcprefix = '_'.join(namespec[1]).lower()

    if isget:
        pref = 'get'
    else:
        pref = 'set'

    ret = _find_regex_per_line(buf, '%s_%s_property\s*\\(' % (funcprefix, pref))

    if not ret:
        ret = _find_class_init(buf, namespec)

        if not ret:
            return None

        mark = buf.create_mark(None, ret, True)

        ret = _find_regex_per_line(buf, '->(finalize|dispose)\s*=')

        if not ret:
            return None

        ret[1].forward_to_line_end()

        buf.insert(ret[1], '\n\n\tobject_class->get_property = %s_get_property;' % (funcprefix,))
        buf.insert(ret[1], '\n\tobject_class->set_property = %s_set_property;\n' % (funcprefix,))

        for i in (['get', ''], ['set', 'const ']):
            ret = buf.get_iter_at_mark(mark)

            s = """static void\n%s_%s_property (GObject *object, guint prop_id, %sGValue *value, GParamSpec *pspec)
{
	%s *self = %s (object);

	switch (prop_id)
	{
		default:
			G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
		break;
	}
}

""" % (funcprefix, i[0], i[1], namespec[0], '_'.join(namespec[1]).upper())

            ret.set_line_offset(0)
            buf.insert(ret, s)

        buf.delete_mark(mark)
        ret = _find_regex_per_line(buf, '%s_%s_property\s*\\(' % (funcprefix, pref))

    ret = _find_regex_per_line(buf, 'default:', ret[1])

    if not ret:
        return None

    ret[0].set_line_offset(0)
    return ret[0]

def add_prop(view, entry, name=None, proptype=None):
    """Add a GObject property: gobj.add-prop [name] [type]

Add a GObject property in a C source file. This adds all the relevant stubs
in the correct places. All property types are supported and can be completed."""
    buf = view.get_buffer()

    namespec = _get_type_name(buf)

    if not namespec:
        raise commander.commands.exceptions.Execute('Could not determine gobject type name...')

    if not name:
        name, words, modifier = (yield commander.commands.result.Prompt('Property name:'))

    name = name.strip().replace('_', '-').replace(' ', '-')
    enumname = name.replace('-', '_').upper()

    start = buf.get_start_iter()

    ret = start.forward_search('PROP_' + enumname, 0)

    if ret:
        raise commander.commands.exceptions.Execute('Property `%s\' already exists' % (name,))

    if not proptype:
        proptype, words, modifier = (yield commander.commands.result.Prompt('Type:', {'*': commander.commands.completion.words(_prop_types.keys())}))

    proptype  = proptype.strip()

    if not proptype in _prop_types:
        return

    nickdef = name.replace('-', ' ').title()

    nick, words, modifier = (yield commander.commands.result.Prompt('Nick [' + nickdef + ']:'))

    if not nick:
        nick = nickdef

    descdef = name.replace('-', ' ').capitalize()

    desc, words, modifier = (yield commander.commands.result.Prompt('Description [' + descdef + ']:'))

    if not desc:
        desc = descdef

    comp = {'*': commander.commands.completion.words(['G_PARAM_READWRITE',
                  'G_PARAM_READABLE',
                  'G_PARAM_WRITABLE',
                  'G_PARAM_READWRITE | G_PARAM_CONSTRUCT',
                  'G_PARAM_READWRITE | G_PARAM_CONSTRUCT_ONLY',
                  'G_PARAM_WRITABLE | G_PARAM_CONSTRUCT'])}

    flags, words, modifier = (yield commander.commands.result.Prompt('Flags [G_PARAM_READWRITE]:', comp))

    if not flags:
        flags = 'G_PARAM_READWRITE'

    pspec = _prop_types[proptype](name, nick, desc, flags)
    yield pspec.read()

    buf.begin_user_action()

    # Find where to insert the relevant parts
    enumins = _find_prop_enum(buf)

    if not enumins:
        buf.end_user_action()
        raise commander.commands.exceptions.Execute('Could not determine where to insert the property enum...')

    enummark = buf.create_mark(None, enumins)

    getins = _find_prop_get_set(buf, namespec, True)

    if not getins:
        buf.delete_mark(enummark)
        buf.end_user_action()
        raise commander.commands.exceptions.Execute('Could not determine the get_property...')

    getmark = buf.create_mark(None, getins)

    setins = _find_prop_get_set(buf, namespec, False)

    if not setins:
        buf.delete_mark(enummark)
        buf.delete_mark(getmark)
        buf.end_user_action()

        raise commander.commands.exceptions.Execute('Could not determine the set_property...')

    setmark = buf.create_mark(None, setins)

    buf.insert(buf.get_iter_at_mark(enummark), ",\n\tPROP_%s" % (enumname))

    if 'READ' in flags:
        buf.insert(buf.get_iter_at_mark(getmark), "\t\tcase PROP_%s:\n\t\t\t/* TODO */\n\t\t\tbreak;\n" % (enumname,))

    if 'WRIT' in flags:
        buf.insert(buf.get_iter_at_mark(setmark), "\t\tcase PROP_%s:\n\t\t\t/* TODO */\n\t\t\tbreak;\n" % (enumname,))

    buf.delete_mark(enummark)
    buf.delete_mark(getmark)
    buf.delete_mark(setmark)

    ret = _find_class_init(buf, namespec)
    ret = _find_regex_per_line(buf, '^}$', ret)

    w = "\n\t".join(pspec.write().splitlines())
    buf.insert(ret[0], "%s\n" % (w,))
    buf.end_user_action()

# vi:ts=4:et

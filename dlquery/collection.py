"""Module containing the logic for the collection of data structure."""

import yaml
import json
import re
from functools import partial
from dlquery.argumenthelper import validate_argument_type
from dlquery import utils
from dlquery.parser import SelectParser
from dlquery.validation import OpValidation
from dlquery.validation import CustomValidation


class ListError(Exception):
    """Use to capture error for List instance"""


class ListIndexError(ListError):
    """Use to capture error for List instance"""


class List(list):
    """This is a class for List Collection.

    Properties:
        is_empty (boolean): a check point to tell an empty list or not.
        first (anything): return a first element of a list
        last (anything): return a last element of a list
        total (int): total element in list

    Exception:
        ListError
    """
    @property
    def is_empty(self):
        """Check an empty list."""
        return self.total == 0

    @property
    def first(self):
        """Get a first element of list if list is not empty"""
        if not self.is_empty:
            return self[0]

        raise ListIndexError('Can not get a first element of an empty list.')

    @property
    def last(self):
        """Get a last element of list if list is not empty"""
        if not self.is_empty:
            return self[-1]
        raise ListIndexError('Can not get last element of an empty list.')

    @property
    def total(self):
        """Get a size of list"""
        return len(self)


class ResultError(Exception):
    """Use to capture error for Result instance."""


class Result:
    """The Result Class to store data.

    Attributes:
        data (anything): the data.
        parent (Result): keyword arguments.

    Properties:
        has_parent -> boolean

    Methods:
        update_parent(parent: Result) -> None

    Exception:
        ResultError
    """
    def __init__(self, data, parent=None):
        self.parent = None
        self.data = data
        self.update_parent(parent)

    def update_parent(self, parent):
        """Update parent to Result

            Parameters:
                parent (Result): a Result instance.

            Return:
                None
        """
        if parent is None or isinstance(parent, self.__class__):
            self.parent = parent
        else:
            msg = 'parent argument must be Result instance or None.'
            raise ResultError(msg)

    @property
    def has_parent(self):
        """Return True if Result has parent."""
        return isinstance(self.parent, Result)


class Element(Result):
    def __init__(self, data, index='', parent=None):
        super().__init__(data, parent=parent)
        self.index = index
        self._build(data)

    def __iter__(self):
        if self.type == 'dict':
            return iter(self.data.keys())
        elif self.type == 'list':
            return iter(range(len(self.data)))
        else:
            fmt = '{!r} object is not iterable.'
            msg = fmt.format(type(self).__name__)
            raise TypeError(msg)

    def __getitem__(self, index):
        if self.type not in ['dict', 'list']:
            fmt = '{!r} object is not subscriptable.'
            msg = fmt.format(type(self).__name__)
            raise TypeError(msg)
        result = self.data[index]
        return result

    def _build(self, data):
        self.children = None
        self.value = None
        if isinstance(data, dict):
            self.type = 'dict'
            lst = List()
            for index, val in data.items():
                elm = Element(val, index=index, parent=self)
                lst.append(elm)
            self.children = lst or None
        elif isinstance(data, (list, tuple, set)):
            self.type = 'list'
            lst = List()
            for i, item in enumerate(data):
                index = '__index__{}'.format(i)
                elm = Element(item, index=index, parent=self)
                lst.append(elm)
            self.children = lst or None
        elif isinstance(data, (int, float, bool, str)) or data is None:
            self.type = type(data).__name__
            self.value = data
        else:
            self.type = 'object'
            self.value = data

    @property
    def has_children(self):
        """Return True if an element has children."""
        return bool(self.children)

    @property
    def is_element(self):
        """Return True if an element has children."""
        return self.has_children

    @property
    def is_leaf(self):
        """Return True if an element doesnt have children."""
        return not self.has_children

    @property
    def is_scalar(self):
        """Return True if an element is a scalar type."""
        return isinstance(self.data, (int, float, bool, str, None))

    @property
    def is_list(self):
        """Return True if an element is a list type."""
        return self.type == 'list'

    @property
    def is_dict(self):
        """Return True if an element is a list type."""
        return self.type == 'dict'

    def filter_result(self, records, select_statement):
        """Filter a list of records based on select statement
        Parameters:
            records (List): a list of record.
            select_statement (str): a select statement.
        Return:
            List: list of filtered records.
        """
        result = List()
        select_obj = SelectParser(select_statement)
        select_obj.parse_statement()

        if callable(select_obj.predicate):
            lst = List()
            for record in records:
                is_found = select_obj.predicate(record.parent.data)
                if is_found:
                    lst.append(record)
        else:
            lst = records[:]

        if select_obj.is_zero_select:
            for item in lst:
                result.append(item.data)
        elif select_obj.is_all_select:
            for item in lst:
                result.append(item.parent.data)
        else:
            for item in lst:
                new_data = item.parent.data.fromkeys(select_obj.columns)
                is_added = True
                for key in new_data:
                    is_added &= key in item.parent.data
                    new_data[key] = item.parent.data.get(key, None)
                is_added and result.append(new_data)
        return result

    def find_(self, node, lookup_obj, result):
        """Recursively search a lookup and store a found record to result
        Parameters:
            node (Element): a Element instance.
            lookup_obj (LookupCls): a LookupCls instance.
            result (List): a found result.
        """
        if node.is_dict or node.is_list:
            for child in node.children:
                if node.is_list:
                    if child.is_element:
                        self.find_(child, lookup_obj, result)
                else:
                    if lookup_obj.is_left_matched(child.index):
                        if lookup_obj.is_right:
                            if lookup_obj.is_right_matched(child.data):
                                result.append(child)
                        else:
                            result.append(child)
                    if child.is_element:
                        self.find_(child, lookup_obj, result)

    def find(self, lookup, select=''):
        """recursively search a lookup.
        Parameter:
            lookup (str): a search pattern.
            select (str): a select statement.
        Return:
            List: list of record
        """
        records = List()
        lkup_obj = LookupCls(lookup)
        self.find_(self, lkup_obj, records)
        result = self.filter_result(records, select)
        return result


class ObjectDict(dict):
    """The ObjectDict can retrieve value of key as attribute style."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update(*args, **kwargs)

    ############################################################################
    # Special methods
    ############################################################################
    def __getattribute__(self, attr):
        try:
            value = super().__getattribute__(attr)
            return value
        except Exception as ex:
            if attr in self:
                return self[attr]
            else:
                raise ex

    def __setitem__(self, key, value):
        new_value = self._build(value)
        super().__setitem__(key, new_value)

    def __setattr__(self, attr, value):
        new_value = self._build(value)
        if attr in self:
            self[attr] = new_value
        else:
            super().__setattr__(attr, new_value)

    ############################################################################
    # Private methods
    ############################################################################
    def _build(self, value, forward=True):
        """The function to recursively build a ObjectDict instance
        when the value is the dict instance.

        Parameters:
            value (anything): The value to recursively build a ObjectDict
                    instance when value is the dict instance.
            forward (boolean): set flag to convert dict instance to ObjectDict
                    instance or vice versa.  Default is True.
        Returns:
            anything: the value or a new value.
        """
        if isinstance(value, (dict, list, set, tuple)):
            if isinstance(value, ObjectDict):
                if forward:
                    return value
                else:
                    result = dict([i, self._build(j, forward=forward)] for i, j in value.items())
                    return result
            elif isinstance(value, dict):
                lst = [[i, self._build(j, forward=forward)] for i, j in value.items()]
                if forward:
                    result = self.__class__(lst)
                    return result
                else:
                    result = dict(lst)
                    return result
            elif isinstance(value, list):
                lst = [self._build(item, forward=forward) for item in value]
                return lst
            elif isinstance(value, set):
                lst = [self._build(item, forward=forward) for item in value]
                return set(lst)
            else:
                tuple_obj = (self._build(item, forward=forward) for item in value)
                return tuple_obj
        else:
            return value

    ############################################################################
    # class methods
    ############################################################################
    @classmethod
    def create_from_json_file(cls, filename, **kwargs):
        """Create a ObjectDict instance from JSON file.
        Parameters:
            filename (string): YAML file.
            kwargs (dict): the keyword arguments.
        """
        from io import IOBase
        if isinstance(filename, IOBase):
            obj = json.load(filename, **kwargs)
        else:
            with open(filename) as stream:
                obj = json.load(stream, **kwargs)

        obj_dict = ObjectDict(obj)
        return obj_dict

    @classmethod
    def create_from_json_data(cls, data, **kwargs):
        obj = json.loads(data, **kwargs)
        obj_dict = ObjectDict(obj)
        return obj_dict

    @classmethod
    def create_from_yaml_file(cls, filename, loader=yaml.SafeLoader):
        """Create a ObjectDict instance from YAML file.
        Parameters:
            filename (string): YAML file.
            loader (yaml.loader.Loader): YAML loader.
        """
        from io import IOBase
        if isinstance(filename, IOBase):
            obj = yaml.load(filename, Loader=loader)
        else:
            with open(filename) as stream:
                obj = yaml.load(stream, Loader=loader)

        obj_dict = ObjectDict(obj)
        return obj_dict

    @classmethod
    def create_from_yaml_data(cls, data, loader=yaml.SafeLoader):
        """Create a ObjectDict instance from YAML data.
        Parameters:
            data (string): YAML data.
            loader (yaml.loader.Loader): YAML loader.
        """
        obj = yaml.load(data, Loader=loader)
        obj_dict = ObjectDict(obj)
        return obj_dict

    ############################################################################
    # public methods
    ############################################################################
    def update(self, *args, **kwargs):
        """Update data to ObjectDict."""
        obj = dict(*args, **kwargs)
        new_obj = dict()
        for key, value in obj.items():
            new_obj[key] = self._build(value)
        super().update(new_obj)

    def deep_apply_attributes(self, node=None, **kwargs):
        """Recursively apply attributes to ObjectDict instance.

        Parameters:
            node (ObjectDict): a ObjectDict instance
            kwargs (dict):
        """

        def assign(node_, **kwargs_):
            for key, val in kwargs_.items():
                setattr(node_, key, val)

        def apply(node_, **kwargs_):
            if isinstance(node_, (dict, list, set, tuple)):
                if isinstance(node_, dict):
                    if isinstance(node_, self.__class__):
                        assign(node_, **kwargs_)
                    for value in node_.values():
                        apply(value, **kwargs_)
                else:
                    for item in node_:
                        apply(item, **kwargs_)

        node = self if node is None else node
        validate_argument_type(self.__class__, node=node)
        apply(node, **kwargs)

    def to_dict(self, data=None):
        """Convert a given data to native dictionary

        Parameters:
            data (ObjectDict): a dynamic dictionary instance.
                if data is None, it will convert current instance to dict.

        Return:
            dict: dictionary
        """
        if data is None:
            data = dict(self)

        validate_argument_type(dict, data=data)
        result = self._build(data, forward=False)
        return result

    todict = to_dict


class LookupClsError(Exception):
    """Use to capture error for LookupObject instance"""


class LookupCls:
    """To build a lookup object."""
    def __init__(self, lookup):
        self.lookup = str(lookup)
        self.left = None
        self.right = None
        self.process()

    @property
    def is_right(self):
        return bool(self.right)

    @classmethod
    def parse(cls, text):
        """Parse a lookup statement.
        Parameters:
            text (str): a lookup.
        Return:
              CustomObject: a object is holding pattern and is_regex attributes.
        """
        def parse_(text_):
            vpat = '''
                _(?P<options>i?)                    # options
                (?P<method>text|wildcard|regex)     # method is wildcard or regex
                [(]
                (?P<pattern>.+)                     # wildcard or regex pattern
                [)]
            '''
            match_ = re.search(vpat, text_, re.VERBOSE)
            options_ = match_.group('options').lower()
            method_ = match_.group('method').lower()
            pattern_ = match_.group('pattern')

            ignorecase_ = 'i' in options_
            if method_ == 'wildcard':
                pattern_ = utils.convert_wildcard_to_regex(pattern_)
            elif method_ == 'text':
                pattern_ = re.escape(pattern_)
            return pattern_, ignorecase_

        def parse_other_(text_):
            vpat1_ = '''
                (?i)(?P<custom_name>
                is_empty|is_not_empty|
                is_mac_address|is_not_mac_address|
                is_ip_address|is_not_ip_address|
                is_ipv4_address|is_not_ipv4_address|
                is_ipv6_address|is_not_ipv6_address|
                is_true|is_not_true|
                is_false|is_not_false)
                [(][)]$
            '''
            vpat2_ = '''
                (?i)(?P<op>lt|le|gt|ge|eq|ne)
                [(]
                (?P<other>([0-9]+)?[.]?[0-9]+)
                [)]$
            '''
            vpat3_ = '''
                (?i)(?P<op>eq|ne)
                [(]
                (?P<other>.*[^0-9].*)
                [)]$
            '''
            data_ = text_.lower()
            match1_ = re.match(vpat1_, data_, flags=re.VERBOSE)
            if match1_:
                custom_name = match1_.group('custom_name')
                valid = False if '_not_' in custom_name else True
                custom_name = custom_name.replace('not_', '')
                method = getattr(CustomValidation, custom_name)
                pfunc = partial(method, valid=valid, on_exception=False)
                return pfunc
            else:
                match2_ = re.match(vpat2_, data_, flags=re.VERBOSE)
                if match2_:
                    op = match2_.group('op')
                    other = match2_.group('other')
                    pfunc = partial(
                        OpValidation.compare_number,
                        op=op, other=other, on_exception=False
                    )
                    return pfunc
                else:
                    match3_ = re.match(vpat3_, data_, flags=re.VERBOSE)
                    if match3_:
                        op = match3_.group('op')
                        other = match3_.group('other')
                        pfunc = partial(
                            OpValidation.compare,
                            op=op, other=other, on_exception=False
                        )
                        return pfunc
                    else:
                        pattern_ = '^{}$'.format(re.escape(text_))
                        return pattern_

        pat = r'_i?(text|wildcard|regex)[(].+[)]'

        if not re.search(pat, text):
            result = parse_other_(text)
            return result
        lst = []
        start = 0
        is_ignorecase = False
        for node in re.finditer(pat, text):
            predata = text[start:node.start()]
            lst.append(re.escape(predata))
            data = node.group()
            pattern, ignorecase = parse_(data)
            lst.append(pattern)
            start = node.end()
            is_ignorecase |= ignorecase
        else:
            if lst:
                postdata = text[start:]
                lst.append(re.escape(postdata))

        pattern = ''.join(lst)
        if pattern:
            ss = '' if pattern[0] == '^' else '^'
            es = '' if pattern[-1] == '$' else '$'
            ic = '(?i)' if is_ignorecase else ''
            pattern = '{}{}{}{}'.format(ic, ss, pattern, es)
            return pattern
        else:
            fmt = 'Failed to parse this lookup : {!r}'
            raise LookupClsError(fmt.format(text))

    def process(self):
        """Parse a lookup to two expressions: a left expression and
        a right expression.
        If a lookup has a right expression, it will parse and assign to right,
        else, right expression is None."""
        left, *lst = self.lookup.split('=', maxsplit=1)
        self.left = self.parse(left)
        if lst:
            self.right = self.parse(lst[0])

    def is_left_matched(self, data):
        if not isinstance(data, str):
            return False
        result = re.search(self.left, data)
        return bool(result)

    def is_right_matched(self, data):
        if not self.right:
            return True
        else:
            if callable(self.right):
                result = self.right(data)
                return result
            else:
                if not isinstance(data, str):
                    return False
                result = re.search(self.right, data)
                return bool(result)

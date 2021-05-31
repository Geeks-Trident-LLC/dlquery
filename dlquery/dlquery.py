"""Module containing the logic for querying dictionary or list object."""
import re
import operator
from dlquery import utils
from dlquery.argumenthelper import validate_argument_type


class DLQueryError(Exception):
    """Use to capture error for DLQuery instance"""


class DLQueryDataTypeError(DLQueryError):
    """Use to capture error of unsupported query data type."""


class DLQuery:
    """This is a class for querying dictionary or list object.

    Attributes:
        data (list, tuple, or dict): list or dictionary instance.

    Properties:
        is_dict -> bool
        is_list -> bool

    Methods:
        keys() -> dict_keys or odict_keys
        values() -> dict_values or odict_values
        items() -> dict_items or odict_items
        get(index, default=None) -> Any

    Exception:
        TypeError
    """

    def __init__(self, data):
        validate_argument_type(list, tuple, dict, data=data)
        self.data = data
        self._is_dict = None
        self._is_list = None

    ############################################################################
    # Special methods
    ############################################################################
    def __len__(self):
        return len(self.data)

    def __getitem__(self, item):
        return self.data[item]

    def __iter__(self):
        if self.is_dict:
            return iter(self.data.keys())
        elif self.is_list:
            return iter(self.data)
        else:
            fmt = '{!r} object is not iterable.'
            msg = fmt.format(type(self).__name__)
            raise TypeError(msg)

    def __bool__(self):
        return bool(self.data)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            result = operator.eq(self.data, other.data)
        else:
            result = operator.eq(self.data, other)
        return result

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            result = operator.ne(self.data, other.data)
        else:
            result = operator.ne(self.data, other)
        return result

    ############################################################################
    # properties
    ############################################################################
    @property
    def is_dict(self):
        """Check if data of DLQuery is a dictionary data."""
        if self._is_dict is None:
            self._is_dict = isinstance(self.data, dict)
        return self._is_dict

    @property
    def is_list(self):
        """Check if data of DLQuery is a list or tuple data."""
        if self._is_list is None:
            self._is_list = isinstance(self.data, (list, tuple))
        return self._is_list

    ############################################################################
    # public methods
    ############################################################################
    def keys(self):
        """a set-like object providing a view on D's keys"""
        result = utils.foreach(self.data, choice='keys')
        return result

    def values(self):
        """a set-like object providing a view on D's values"""
        result = utils.foreach(self.data, choice='values')
        return result

    def items(self):
        """a set-like object providing a view on D's items"""
        result = utils.foreach(self.data, choice='items')
        return result

    def get(self, index, default=None, on_exception=False):
        """if DLQuery is a list, then return the value for index if
        index is in the list, else default.

        if DLQuery is a dictionary, then return the value for key (i.e index)
        if key is in the dictionary, else default.

        Parameters:
            index (int, str): a index of list or a key of dictionary.
            default (Any): a default value if no element in list or
                    in dictionary is found.
            on_exception (bool): raise Exception if it is True.  Default is False.
        Return:
            Any: any value from DLQuery.data
        """
        try:
            if self.is_list:
                if isinstance(index, int):
                    return self.data[index]
                elif isinstance(index, str):
                    pattern = r'-?[0-9]+$'
                    if re.match(pattern, index.strip()):
                        return self.data[int(index)]
                    else:
                        count = index.count(':')
                        if count == 1:
                            i, j = [x.strip() for x in index.split(':')]
                            chks = [
                                re.match(pattern, i.strip()) or i == '',
                                re.match(pattern, j.strip()) or j == ''
                            ]
                            if any(chks):
                                i = int(i) if i else None
                                j = int(j) if j else None
                                slice_obj = slice(i, j)
                                return self.data[slice_obj]
                            else:
                                if on_exception:
                                    return self.data[index]
                                else:
                                    return default
                        elif count == 2:
                            i, j, k = [x.strip() for x in index.split(':')]
                            chks = [
                                re.match(pattern, i.strip()) or i == '',
                                re.match(pattern, j.strip()) or j == '',
                                re.match(pattern, k.strip()) or k == ''
                            ]
                            if any(chks):
                                i = int(i) if i else None
                                j = int(j) if j else None
                                k = int(k) if k else None
                                slice_obj = slice(i, j, k)
                                return self.data[slice_obj]
                            else:
                                if on_exception:
                                    return self.data[index]
                                else:
                                    return default
                        else:
                            if on_exception:
                                return self.data[index]
                            else:
                                return default
                else:
                    return default
            else:
                key = index
                return self.data.get(key, default)
        except Exception as ex:     # noqa
            if on_exception:
                raise ex
            else:
                return default

#-*- coding: utf-8 -*-
# pylint: disable=protected-access, too-few-public-methods, no-member

"""This module is used by the `model <#module-half_orm.model>`_ module
to generate the classes that manipulate the data in your database
with the `Model.get_relation_class <#half_orm.model.Model.get_relation_class>`_
method.


Example:
    >>> from half_orm.model import Model
    >>> model = Model('halftest')
    >>> class Person(model.get_relation_class('actor.person')):
    >>>     # your code goes here
"""

"""
Main methods provided by the class Relation:
- insert: inserts a tuple into the pg table.
- select: returns a generator of the elements of the set defined by
  the constraint on the Relation object. The elements are dictionaries with the
  keys corresponding to the selected columns names in the relation.
  The result is affected by the methods: _ho_distinct, _ho_order_by, _ho_limit and _ho_offset
  (see below).
- update: updates the set defined by the constraint on the Relation object
  with the values passed as arguments.
- delete: deletes from the relation the set of elements defined by the constraint
  on the Relation object.
- get: returns the unique element defined by the constraint on the Relation object.
  the element returned if of the type of the Relation object.
- count: returns the number of elements in the set defined by the constraint on the
  Relation object.

The following methods can be chained on the object before a select.

- _ho_distinct: ensures that there are no duplicates on the select result.
- _ho_order_by: sets the order of the select result.
- _ho_limit: limits the number of elements returned by the select method.
- _ho_offset: sets the offset for the select method.

"""

from functools import wraps
from collections import OrderedDict
from uuid import UUID
from typing import Generator, List
from datetime import date, datetime, time, timedelta
import json
import sys
import psycopg2
from psycopg2.extras import RealDictCursor


import yaml

from half_orm import relation_errors
from half_orm.transaction import Transaction
from half_orm.field import Field
from half_orm.packager import utils

class _SetOperators:
    """_SetOperators class stores the set operations made on the Relation class objects

    - __operator is one of {'or', 'and', 'sub', 'neg'}
    - __right is a Relation object. It can be None if the operator is 'neg'.
    """
    def __init__(self, left, operator=None, right=None):
        self.__left = left
        self.__operator = operator
        self.__right = right

    @property
    def operator(self):
        """Property returning the __operator value."""
        return self.__operator
    @operator.setter
    def operator(self, operator):
        """Set operator setter."""
        self.__operator = operator

    @property
    def left(self):
        """Returns the left object of the set operation."""
        return self.__left
    @left.setter
    def left(self, left):
        """left operand (relation) setter."""
        self.__left = left

    @property
    def right(self):
        """Property returning the right operand (relation)."""
        return self.__right
    @right.setter
    def right(self, right):
        """right operand (relation) setter."""
        self.__right = right

    # def __repr__(self):
    #     return f"{self.__operator} {self.__right and self.__right._fqrn or None}"

class Relation:
    """Used as a base class for the classes generated by
    `Model.get_relation_class <#half_orm.model.Model.get_relation_class>`_.

    Args:
        **kwargs: the arguments names must correspond to the columns names of the relation.

    Raises:
        UnknownAttributeError: If the name of an argument doesn't match a column name in the
            relation considered.

    Examples:
        You can generate a class for any relation in your database:
            >>> from half_orm.model import Model
            >>> model = Model('halftest')
            >>> class Person(model.get_relation_class('actor.person')):
            >>>     # your code

        To define a set of data in your relation at instantiation:
            >>> gaston = Person(last_name='Lagaffe', first_name='Gaston')
            >>> all_names_starting_with_la = Person(last_name=('ilike', 'la%'))

        Or to constrain an instantiated object via its\
            `Fields <#half_orm.field.Field>`_:
            >>> person = Person()
            >>> person.birth_date = ('>', '1970-01-01')

        Raises an `UnknownAttributeError <#half_orm.relation_errors.UnknownAttributeError>`_:
            >>> Person(lost_name='Lagaffe')
            [...]UnknownAttributeError: ERROR! Unknown attribute: {'lost_name'}.
    """

#### THE following METHODS are included in Relation class according to
#### relation type (Table or View). See TABLE_INTERFACE and VIEW_INTERFACE.

def __init__(self, **kwargs):
    _fqrn = ""
    """The arguments names must correspond to the columns names of the relation.
    """
    self._ho_fields = {}
    self._ho_pkey = {}
    self._ho_fkeys = OrderedDict()
    self._ho_fkeys_attr = set()
    self._ho_join_to = {}
    self._ho_is_singleton = False
    self.__only = False
    self.__neg = False
    self.__set_fields()
    self.__set_fkeys()
    self.__query = ""
    self.__query_type = None
    self.__sql_query = []
    self.__sql_values = []
    self.__set_operators = _SetOperators(self)
    self.__select_params = {}
    self.__id_cast = None
    self.__cursor = self._model._connection.cursor(cursor_factory=RealDictCursor)
    self.__cons_fields = []
    self.__mogrify = False
    kwk_ = set(kwargs.keys())
    if kwk_.intersection(self._ho_fields.keys()) != kwk_:
        raise relation_errors.UnknownAttributeError(str(kwk_.difference(self._ho_fields.keys())))
    _ = {self.__dict__[field_name]._set(value)
         for field_name, value in kwargs.items() if value is not None}
    self.__isfrozen = True

@utils.trace
def _ho_insert(self, *args) -> '[dict]':
    """Insert a new tuple into the Relation.

    Returns:
        [dict]: A singleton containing the data inserted.

    Example:
        >>> gaston = Person(last_name='Lagaffe', first_name='Gaston', birth_date='1970-01-01')._ho_insert()
        >>> print(gaston)
        {'id': 1772, 'first_name': 'Gaston', 'last_name': 'Lagaffe', 'birth_date': datetime.date(1970, 1, 1)}

    Note:
        It is not possible to insert more than one row with the insert method
    """
    query_template = "insert into {} ({}) values ({})"
    self.__query_type = 'insert'
    fields_names, values, fk_fields, fk_query, fk_values = self.__what()
    what_to_insert = ["%s" for _ in range(len(values))]
    if fk_fields:
        fields_names += fk_fields
        what_to_insert += fk_query
        values += fk_values
    query = query_template.format(self._qrn, ", ".join(fields_names), ", ".join(what_to_insert))
    returning = args or ['*']
    if returning:
        query = self.__add_returning(query, *returning)
    self.__execute(query, tuple(values))
    res = [dict(elt) for elt in self.__cursor.fetchall()] or [{}]
    return res[0]

@utils.trace
def _ho_select(self, *args):
    """Gets the set of values correponding to the constraint attached to the object.
    This method is a generator.

    Arguments:
        *args: the fields names of the returned attributes. If omitted,
            all the fields are returned.

    Yields:
        the result of the query as a dictionary.

    Example:
        >>> for person in Person(last_name=('like', 'La%'))._ho_select('id'):
        >>>     print(person)
        {'id': 1772}
    """
    query, values = self._ho_prep_select(*args)
    self.__execute(query, values)
    for elt in self.__cursor:
        yield dict(elt)

@utils.trace
def _ho_get(self, *args: List[str]) -> Relation:
    """The get method allows you to fetch a singleton from the database.
    It garantees that the constraint references one and only one tuple.

    Args:
        args (List[str]): list of fields names.\
        If ommitted, all the values of the row retreived from the database\
        are set for the self object.\
        Otherwise, only the values listed in the `args` parameter are set.

    Returns:
        Relation: the object retreived from the database.

    Raises:
        ExpectedOneError: an exception is raised if no or more than one element is found.

    Example:
        >>> gaston = Person(last_name='Lagaffe', first_name='Gaston')._ho_get()
        >>> type(gaston) is Person
        True
        >>> gaston.id
        (int4) NOT NULL (id = 1772)
        >>> str(gaston.id)
        '1772'
        >>> gaston.id.value
        1772
    """
    _count = len(self)
    if _count != 1:
        raise relation_errors.ExpectedOneError(self, _count)
    self._ho_is_singleton = True
    ret = self(**(next(self._ho_select(*args))))
    ret._ho_is_singleton = True
    return ret

@utils.trace
def __fkey_where(self, where, values):
    _, _, fk_fields, fk_query, fk_values = self.__what()
    if fk_fields:
        fk_where = " and ".join([f"({a}) in ({b})" for a, b in zip(fk_fields, fk_query)])
        if fk_where:
            if where:
                where = f"{where} and {fk_where}"
            else:
                where = fk_where
        values += fk_values
    return where, values

@utils.trace
def _ho_update(self, *args, update_all=False, **kwargs):
    """
    kwargs represents the values to be updated {[field name:value]}
    The object self must be set unless update_all is True.
    The constraints of self are updated with kwargs.
    """
    if not (self._ho_is_set() or update_all):
        raise RuntimeError(
            f'Attempt to update all rows of {self.__class__.__name__}'
            ' without update_all being set to True!')

    update_args = dict(kwargs)
    for key, value in kwargs.items():
        # None values are first removed
        if value is None: # pragma: no cover
            update_args.pop(key)
    if not update_args:
        return None # no new value update. Should we raise an error here?

    query_template = "update {} set {} {}"
    what, where, values = self.__update_args(**update_args)
    where, values = self.__fkey_where(where, values)
    query = query_template.format(self._qrn, what, where)
    if args:
        query = self.__add_returning(query, *args)
    self.__execute(query, tuple(values))
    for field_name, value in update_args.items():
        self._ho_fields[field_name]._set(value)
    if args:
        return [dict(elt) for elt in self.__cursor.fetchall()]

@utils.trace
def _ho_delete(self, *args, delete_all=False):
    """Removes a set of tuples from the relation.
    To empty the relation, delete_all must be set to True.
    """
    if not (self._ho_is_set() or delete_all):
        raise RuntimeError(
            f'Attempt to delete all rows from {self.__class__.__name__}'
            ' without delete_all being set to True!')
    query_template = "delete from {} {}"
    _, values = self.__get_query(query_template)
    print('XXX __get_query _', _)
    self.__query_type = 'delete'
    _, where, _ = self.__where_args()
    print('XXX where delete', where)
    where, values = self.__fkey_where(where, values)
    if where:
        where = f" where {where}"
    query = f"delete from {self._qrn} {where}"
    if args:
        query = self.__add_returning(query, *args)
    self.__execute(query, tuple(values))
    if args:
        return [dict(elt) for elt in self.__cursor.fetchall()]

@staticmethod
def __add_returning(query, *args) -> str:
    "Adds the SQL returning clause to the query"
    if args:
        returning = ', '.join(args)
        return f'{query} returning {returning}'
    return query

def _ho_unfreeze(self):
    "Allow to add attributs to a relation"
    self.__isfrozen = False

def _ho_freeze(self):
    "set __isfrozen to True."
    self.__isfrozen = True

def __setattr__(self, key, value):
    """Sets an attribute as long as __isfrozen is False

    The foreign keys properties are not detected by hasattr
    hence the line `_ = self.__dict__[key]` to double check if
    the attribute is really present.
    """
    if not hasattr(self, '__isfrozen'):
        object.__setattr__(self, '__isfrozen', False)
    if self.__isfrozen and not hasattr(self, key):
        raise relation_errors.IsFrozenError(self.__class__, key)
    if self.__dict__.get(key) and isinstance(self.__dict__[key], Field):
        self.__dict__[key]._set(value)
        return
    object.__setattr__(self, key, value)

@utils.trace
def __execute(self, query, values):
    try:
        if self.__mogrify:
            print(self.__cursor.mogrify(query, values).decode('utf-8'))
        return self.__cursor.execute(query, values)
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        self._model.ping()
        self.__cursor = self._model._connection.cursor(cursor_factory=RealDictCursor)
        return self.__cursor.execute(query, values)

@property
def _ho_id(self):
    """Return the __id_cast or the id of the relation.
    """
    return self.__id_cast or id(self)

@property
def _ho_only(self):
    "Returns the value of self.__only"
    return self.__only
@_ho_only.setter
def _ho_only(self, value):
    """Set the value of self.__only. Restrict the values of a query to
    the elements of the relation (no inherited values).
    """
    if not value in {True, False}:
        raise ValueError(f'{value} is not a bool!')
    self.__only = value

def __set_fields(self):
    """Initialise the fields of the relation."""
    _fields_metadata = self._model._fields_metadata(self._t_fqrn)

    for field_name, f_metadata in _fields_metadata.items():
        field = Field(field_name, self, f_metadata)
        self._ho_fields[field_name] = field
        setattr(self, field_name, field)
        if field._is_part_of_pk():
            self._ho_pkey[field_name] = field

def __set_fkeys(self):
    """Initialisation of the foreign keys of the relation"""
    #pylint: disable=import-outside-toplevel
    from half_orm.fkey import FKey

    _fkeys_metadata = self._model._fkeys_metadata(self._t_fqrn)
    for fkeyname, f_metadata in _fkeys_metadata.items():
        self._ho_fkeys[fkeyname] = FKey(fkeyname, self, *f_metadata)
    if hasattr(self.__class__, 'Fkeys') and not self.__fkeys_properties:
        # if not hasattr(self.__class__.__base__, 'Fkeys'):
        #     setattr(self.__class__.__base__, 'Fkeys', self.__class__.Fkeys)
        for key, value in self.Fkeys.items():
            try:
                if key != '': # we skip empty keys
                    setattr(self, key, self._ho_fkeys[value])
                    self._ho_fkeys_attr.add(key)
            except KeyError as exp:
                raise relation_errors.WrongFkeyError(self, value) from exp
    self.__fkeys_properties = True

def _ho_group_by(self, yml_directive): #pragma: no cover
    """Returns an aggregation of the data according to the yml directive
    description.
    """
    utils.error("Use at your own risk. This method is not tested.\n")
    def inner_group_by(data, directive, grouped_data, gdata=None):
        """recursive fonction to actually group the data in grouped_data."""
        deja_vu_key = set()
        if gdata is None:
            gdata = grouped_data
        if isinstance(directive, list):
            directive = directive[0]
        keys = set(directive)
        for elt in data:
            res_elt = {}
            for key in keys.intersection(self._ho_fields.keys()):
                deja_vu_key.add(directive[key])
                try:
                    res_elt.update({directive[key]:elt[key]})
                except KeyError as exc:
                    raise relation_errors.UnknownAttributeError(key) from exc
            if isinstance(gdata, list):
                different = None
                for selt in gdata:
                    different = True
                    for key in deja_vu_key:
                        different = selt[key] != res_elt[key]
                        if different:
                            break
                    if not different:
                        break
                if not gdata or different:
                    gdata.append(res_elt)
            else:
                gdata.update(res_elt)
            for group_name in keys.difference(
                    keys.intersection(self._ho_fields.keys())):
                type_directive = type(directive[group_name])
                suite = None
                if not gdata:
                    gdata[group_name] = type_directive()
                    suite = gdata[group_name]
                elif isinstance(gdata, list):
                    suite = None
                    for selt in gdata:
                        different = True
                        for skey in deja_vu_key:
                            different = selt[skey] != res_elt[skey]
                            if different:
                                break
                        if not different:
                            if selt.get(group_name) is None:
                                selt[group_name] = type_directive()
                            suite = selt[group_name]
                            break
                    if suite is None:
                        gdata.append(res_elt)
                elif gdata.get(group_name) is None:
                    #TODO: Raise ExpectedOneError if necessary
                    gdata[group_name] = type_directive()
                    suite = gdata[group_name]
                else:
                    suite = gdata[group_name]
                inner_group_by(
                    [elt], directive[group_name], suite, None)

    grouped_data = {}
    data = list(self)
    directive = yaml.safe_load(yml_directive)
    inner_group_by(data, directive, grouped_data)
    return grouped_data

def _ho_json(self, yml_directive=None, res_field_name='elements', **kwargs): #pragma: no cover
    """Returns a JSON representation of the set returned by the select query.
    if kwargs, returns {res_field_name: [list of elements]}.update(kwargs)
    """
    utils.error("Use at your own risk. This method is not tested.\n")

    def handler(obj):
        """Replacement of default handler for json.dumps."""
        if hasattr(obj, 'isoformat'):
            return str(obj.isoformat())
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, timedelta):
            return obj.total_seconds()
        raise TypeError(
            f'Object of type {type(obj)} with value of {repr(obj)} is not JSON serializable')

    if yml_directive:
        res = self._ho_group_by(yml_directive)
    else:
        res = list(self)
    if kwargs:
        res = {res_field_name: res}
        res.update(kwargs)
    return json.dumps(res, default=handler)

def _ho_dict(self):
    """Returns a dictionary containing only the values of the fields
    that are set."""
    return {key:field.value for key, field in self._ho_fields.items() if field.is_set()}

def __to_dict_val_comp(self):
    """Returns a dictionary containing the values and comparators of the fields
    that are set."""
    return {key:(field._comp(), field.value) for key, field in
            self._ho_fields.items() if field.is_set()}

def __repr__(self):

    fkeys_usage = """To use the foreign keys as direct attributes of the class, copy/paste the Fkeys below into
your code as a class attribute and replace the empty string key(s) with the alias(es) you
want to use. The aliases must be unique and different from any of the column names. Empty
string keys are ignored.

Fkeys = {"""

    rel_kind = self.__kind
    ret = []
    ret.append(f"__RCLS: {self.__class__}")
    ret.append(
        "This class allows you to manipulate the data in the PG relation:")
    ret.append(f"{rel_kind.upper()}: {self._fqrn}")
    if self.__metadata['description']:
        ret.append(f"DESCRIPTION:\n{self.__metadata['description']}")
    ret.append('FIELDS:')
    mx_fld_n_len = 0
    for field_name in self._ho_fields.keys():
        if len(field_name) > mx_fld_n_len:
            mx_fld_n_len = len(field_name)
    for field_name, field in self._ho_fields.items():
        ret.append(f"- {field_name}:{' ' * (mx_fld_n_len + 1 - len(field_name))}{repr(field)}")
    ret.append('')
    pkey = self._model._pkey_constraint(self._t_fqrn)
    if pkey:
        ret.append(f"PRIMARY KEY ({', '.join(pkey)})")
    for uniq in self._model._unique_constraints_list(self._t_fqrn):
        ret.append(f"UNIQUE CONSTRAINT ({', '.join(uniq)})")
    if self._ho_fkeys.keys():
        plur = 'S' if len(self._ho_fkeys) > 1 else ''
        ret.append(f'FOREIGN KEY{plur}:')
        for fkey in self._ho_fkeys.values():
            ret.append(repr(fkey))
        ret.append('')
        ret.append(fkeys_usage)
        for fkey in self._ho_fkeys:
            ret.append(f"    '': '{fkey}',")
        ret.append('}')
    return '\n'.join(ret)

def _ho_is_set(self):
    """Return True if one field at least is set or if self has been
    constrained by at least one of its foreign keys or self is the
    result of a combination of Relations (using set operators).
    """
    joined_to = False
    for _, jt_ in self._ho_join_to.items():
        joined_to |= jt_._ho_is_set()
    return (joined_to or bool(self.__set_operators.operator) or bool(self.__neg) or
            bool({field for field in self._ho_fields.values() if field.is_set()}))

def __get_set_fields(self):
    """Returns a list containing only the fields that are set."""
    return [field for field in self._ho_fields.values() if field.is_set()]

@utils.trace
def __walk_op(self, rel_id_, out=None, _fields_=None):
    """Walk the set operators tree and return a list of SQL where
    representation of the query with a list of the fields of the query.
    """
    if out is None:
        out = []
        _fields_ = []
    if self.__set_operators.operator:
        if self.__neg:
            out.append("not (")
        out.append("(")
        left = self.__set_operators.left
        left.__query_type = self.__query_type
        left.__walk_op(rel_id_, out, _fields_)
        if self.__set_operators.right is not None:
            out.append(f" {self.__set_operators.operator}\n    ")
            right = self.__set_operators.right
            right.__query_type = self.__query_type
            right.__walk_op(rel_id_, out, _fields_)
        out.append(")")
        if self.__neg:
            out.append(")")
    else:
        out.append(self.__where_repr(rel_id_))
        _fields_ += self.__get_set_fields()
    return out, _fields_

def __sql_id(self):
    """Returns the FQRN as alias for the sql query."""
    return f"{self._qrn} as r{self._ho_id}"

@utils.trace
def __get_from(self, orig_rel=None, deja_vu=None):
    """Constructs the __sql_query and gets the __sql_values for self."""
    if deja_vu is None:
        orig_rel = self
        self.__sql_query = [__sql_id(self)]
        deja_vu = {self._ho_id:[(self, None)]}
    for fkey, fk_rel in self._ho_join_to.items():
        fk_rel.__query_type = orig_rel.__query_type
        if fk_rel._ho_id not in deja_vu:
            deja_vu[fk_rel._ho_id] = []
        elif (fk_rel, fkey) in deja_vu[fk_rel._ho_id] or fk_rel is orig_rel:
            #sys.stderr.write(f"déjà vu in from! {fk_rel._fqrn}\n")
            continue
        fk_rel.__get_from(orig_rel, deja_vu)
        deja_vu[fk_rel._ho_id].append((fk_rel, fkey))
        if fk_rel.__set_operators.operator:
            fk_rel.__get_from(self._ho_id)
        _, where, values = fk_rel.__where_args()
        where = f" and\n    {where}"
        orig_rel.__sql_query.insert(1, f'\n  join {__sql_id(fk_rel)} on\n   ')
        orig_rel.__sql_query.insert(2, fkey._join_query(self))
        orig_rel.__sql_query.append(where)
        orig_rel.__sql_values += values

@utils.trace
def __where_repr(self, rel_id_):
    where_repr = []
    for field in self.__get_set_fields():
        where_repr.append(field._where_repr(self.__query_type, rel_id_))
    where_repr = ' and '.join(where_repr) or '1 = 1'
    ret = f"({where_repr})"
    if self.__neg:
        ret = f"not ({ret})"
    return ret

@utils.trace
def __where_args(self, *args):
    """Returns the what, where and values needed to construct the queries.
    """
    rel_id_ = self._ho_id
    what = f'r{rel_id_}.*'
    if args:
        what = ', '.join([f'r{rel_id_}.{arg}' for arg in args])
    s_where, set_fields = self.__walk_op(rel_id_)
    s_where = ''.join(s_where)
    if s_where == '()':
        s_where = '(1 = 1)'
    return what, s_where, set_fields

@utils.trace
def __get_query(self, query_template, *args):
    """Prepare the SQL query to be executed."""
    from half_orm.fkey import FKey

    self.__sql_values = []
    self.__query_type = 'select'
    what, where, values = self.__where_args(*args)
    where = f"\nwhere\n    {where}"
    self.__get_from()
    # remove duplicates
    for idx, elt in reversed(list(enumerate(self.__sql_query))):
        if elt.find('\n  join ') == 0 and self.__sql_query.count(elt) > 1:
            self.__sql_query[idx] = '  and\n'
    # check that fkeys are fkeys
    for fkey_name in self._ho_fkeys_attr:
        fkey_cls = self.__dict__[fkey_name].__class__
        if fkey_cls != FKey:
            raise RuntimeError(
                f'self.{fkey_name} is not a FKey (got a {fkey_cls.__name__} object instead).\n'
                f'- use: self.{fkey_name}.set({fkey_cls.__name__}(...))\n'
                f'- not: self.{fkey_name} = {fkey_cls.__name__}(...)'
                )
    return (
        query_template.format(
            what,
            self.__only and "only" or "",
            ' '.join(self.__sql_query), where),
        values)

@utils.trace
def _ho_prep_select(self, *args):
    self.__sql_values = []
    query_template = f"select\n {self.__select_params.get('distinct', '')} {{}}\nfrom\n  {{}} {{}}\n  {{}}"
    query, values = self.__get_query(query_template, *args)
    values = tuple(self.__sql_values + values)
    if 'order_by' in self.__select_params.keys():
        query = f"{query} order by {self.__select_params['order_by']}"
    if 'limit' in self.__select_params.keys():
        query = f"{query} limit {self.__select_params['limit']}"
    if 'offset' in self.__select_params.keys():
        query = f"{query} offset {self.__select_params['offset']}"
    return query, values

def _ho_distinct(self):
    """Set distinct in SQL select request."""
    self.__select_params['distinct'] = 'distinct'
    return self

def _ho_unaccent(self, *fields_names):
    "Sets unaccent for each field listed in fields_names"
    for field_name in fields_names:
        if not isinstance(self.__dict__[field_name], Field):
            raise ValueError(f'{field_name} is not a Field!')
        self.__dict__[field_name].unaccent = True
    return self

def _ho_order_by(self, _order_):
    """Set SQL order by according to the "order" string passed

    @order string example :
    "field1, field2 desc, field3, field4 desc"
    """
    self.__select_params['order_by'] = _order_
    return self

def _ho_limit(self, _limit_):
    """Set limit for the next SQL select request."""
    if _limit_:
        self.__select_params['limit'] = _limit_
    elif 'limit' in self.__select_params:
        self.__select_params.pop('limit')
    return self

def _ho_offset(self, _offset_):
    """Set the offset for the next SQL select request."""
    self.__select_params['offset'] = _offset_
    return self

def _ho_mogrify(self):
    """Prints the select query."""
    self.__mogrify = True
    return self

def __len__(self):
    """Returns the number of tuples matching the intention in the relation.

    See select for arguments.
    """
    self.__query = "select"
    query_template = "select\n  count(distinct {})\nfrom {}\n  {}\n  {}"
    query, values = self.__get_query(query_template)
    vars_ = tuple(self.__sql_values + values)
    self.__execute(query, vars_)
    return self.__cursor.fetchone()['count']

def _ho_is_empty(self):
    """Returns True if the relation is empty, False otherwise.

    Same as __len__ but limits the request to 1 element (faster).
    Use it instead of len(relation) == 0.
    """
    self.__query = "select"
    query_template = "select\n  count(distinct {})\nfrom {}\n  {}\n  {} limit 1"
    query, values = self.__get_query(query_template)
    vars_ = tuple(self.__sql_values + values)
    self.__execute(query, vars_)
    return self.__cursor.fetchone()['count'] != 1

@utils.trace
def __update_args(self, **kwargs):
    """Returns the what, where an values for the update query."""
    what_fields = []
    new_values = []
    self.__query_type = 'update'
    _, where, values = self.__where_args()
    where = f" where {where}"
    for field_name, new_value in kwargs.items():
        what_fields.append(field_name)
        new_values.append(new_value)
    what = ", ".join([f'"{elt}" = %s' for elt in what_fields])
    return what, where, new_values + values

@utils.trace
def __what(self):
    """Returns the constrained fields and foreign keys.
    """
    fields_names = []
    set_fields = self.__get_set_fields()
    if set_fields:
        fields_names = [
            f'"{name}"' for name, field in self._ho_fields.items() if field.is_set()]
    fk_fields = []
    fk_queries = ''
    fk_values = []
    for fkey in self._ho_fkeys.values():
        fk_prep_select = fkey._fkey_prep_select()
        if fk_prep_select is not None:
            fk_values += list(fkey.values()[0])
            fk_fields += fk_prep_select[0]
            fk_queries = ["%s" for _ in range(len(fk_values))]

    return fields_names, set_fields, fk_fields, fk_queries, fk_values

def __call__(self, **kwargs):
    return self.__class__(**kwargs)

def _ho_cast(self, qrn):
    """Cast a relation into another relation.

    TODO: check that qrn inherits self (or is inherited by self)?
    """
    new = self._model._import_class(qrn)(**self.__to_dict_val_comp())
    new.__id_cast = id(self)
    new._ho_join_to = self._ho_join_to
    new.__set_operators = self.__set_operators
    return new

def _ho_join(self, *f_rels):
    """Joins data to self._ho_select() result. Returns a dict
    f_rels is a list of [(obj: Relation(), name: str, fields: Optional(<str|str[]>)), ...].

    Each obj in f_rels must have a direct or reverse fkey to self.
    If res is the result, res[name] contains the data associated to the element
    through the fkey or reversed fkey.
    If fields is a str, the data associated with res[name] is returned in a list (only one column).
    Otherwise (str[]), res[name] is a list of dict.
    If the fields argument is ommited, all the fields of obj are returned in a list of dict.

    Raises:
        RuntimeError: if self.__class__ and foreign.__class__ don't have fkeys to each other.

    Returns:
        dict: all values are converted to string.
    """
    from half_orm.fkey import FKey

    def to_str(value):
        """Returns value in string format if the type of value is
        in TO_PROCESS

        Args:
            value (any): the value to return in string format.
        """

        TO_PROCESS = {UUID, date, datetime, time, timedelta}
        if value.__class__ in TO_PROCESS:
            return str(value)
        return value

    res = list(
        {key: to_str(value) for key, value in elt.items()}
        for elt in self._ho_distinct()
    )
    result_as_list = False
    ref = self()
    for f_rel in f_rels:
        if not isinstance(f_rel, tuple):
            raise RuntimeError("f_rels must be a list of tuples.")
        if len(f_rel) == 3:
            f_relation, name, fields = f_rel
        elif len(f_rel) == 2:
            f_relation, name = f_rel
            fields = list(f_relation._ho_fields.keys())
        else:
            raise RuntimeError(f"f_rel must have 2 or 3 arguments. Got {len(f_rel)}.")
        if isinstance(fields, str):
            fields = [fields]
            result_as_list = True
        res_remote = {}

        f_relation_fk_names = []
        fkey_found = False
        for fkey_12 in ref._ho_fkeys:
            if type(ref._ho_fkeys[fkey_12]) != FKey: #pragma: no cover
                raise RuntimeError("This is not an Fkey")
            remote_fk = ref._ho_fkeys[fkey_12]
            remote = remote_fk()
            if remote.__class__ == f_relation.__class__:
                for field in f_relation._ho_fields.keys():
                    if f_relation.__dict__[field].is_set():
                        remote.__dict__[field]._set(f_relation.__dict__[field])
                fkey_found = True
                f_relation_fk_names = remote_fk.fk_names
                break

        if not fkey_found:
            raise RuntimeError(f"No foreign key between {self._fqrn} and {f_relation._fqrn}!")
        inter = [{key: to_str(val) for key, val in elt.items()}
            for elt in remote._ho_distinct()._ho_select(
                *([f'"{field}"' for field in fields] + f_relation_fk_names))]
        for elt in inter:
            key = tuple(elt[subelt] for subelt in f_relation_fk_names)
            if key not in res_remote:
                res_remote[key] = []
            if result_as_list:
                res_remote[key].append(to_str(elt[fields[0]]))
            else:
                res_remote[key].append({key: to_str(elt[key]) for key in fields})

        if f_relation_fk_names:
            d_res = {
                tuple(elt[selt] for selt in remote_fk.names): elt
                for elt in res
                }
            to_remove = set()
            for elt in d_res:
                remote = res_remote.get(elt)
                if remote:
                    d_res[elt][name] = remote
                else:
                    to_remove.add(elt)
            res = [elt for elt in res if tuple(elt[selt]
                    for selt in remote_fk.names) not in to_remove]
    return res

def __set__op__(self, operator=None, right=None):
    """Si l'opérateur du self est déjà défini, il faut aller modifier
    l'opérateur du right ???
    On crée un nouvel objet sans contrainte et on a left et right et opérateur
    """
    def check_fk(new, jt_list):
        """Sets the _ho_join_to dictionary for the new relation.
        """
        for fkey, rel in jt_list.items():
            if rel is self:
                rel = new
            new._ho_join_to[fkey] = rel
    new = self(**self.__to_dict_val_comp())
    new.__id_cast = self.__id_cast
    if operator:
        new.__set_operators.left = self
        new.__set_operators.operator = operator
    dct_join = self._ho_join_to
    if right is not None:
        new.__set_operators.right = right
        dct_join.update(right._ho_join_to)
    check_fk(new, dct_join)
    return new

def __and__(self, right):
    return self.__set__op__("and", right)
def __iand__(self, right):
    self = self & right
    return self

def __or__(self, right):
    return self.__set__op__("or", right)
def __ior__(self, right):
    self = self | right
    return self

def __sub__(self, right):
    return self.__set__op__("and not", right)
def __isub__(self, right):
    self = self - right
    return self

def __neg__(self):
    new = self.__set__op__(self.__set_operators.operator, self.__set_operators.right)
    new.__neg = not self.__neg
    return new

def __xor__(self, right):
    return (self | right) - (self & right)
def __ixor__(self, right):
    self = self ^ right
    return self

def __contains__(self, right):
    return len(right - self) == 0

def __eq__(self, right):
    if id(self) == id(right):
        return True
    return self in right and right in self

def __ne__(self, right):
    return not self == right

def __enter__(self):
    """Context management entry

    Returns self in a transaction context.

    Example usage:
    with relation as rel:
        rel._ho_update(col=new_val)

    Equivalent to (in a transaction context):
    rel = relation._ho_select()
    for elt in rel:
        new_elt = relation(**elt)
        new_elt._ho_update(col=new_val)
    """
    self._ho_transaction._enter(self._model)
    return self

def __exit__(self, *__):
    """Context management exit

    """
    self._ho_transaction._exit(self._model)
    return False

def __iter__(self):
    return self._ho_select()

def __next__(self):
    return next(self._ho_select())

def singleton(fct):
    """Decorator. Enforces the relation to define a singleton.

    _ho_is_singleton is set by Relation.get.
    _ho_is_singleton is unset as soon as a Field is set.
    """
    @wraps(fct)
    def wrapper(self, *args, **kwargs):
        if self._ho_is_singleton:
            return fct(self, *args, **kwargs)
        try:
            self = self._ho_get()
            return fct(self, *args, **kwargs)
        except relation_errors.ExpectedOneError as err:
            raise relation_errors.NotASingletonError(err)
    return wrapper

#### Deprecated

#### END of Relation methods definition

COMMON_INTERFACE = {
    '__init__': __init__,
    '__setattr__': __setattr__,
    '__execute': __execute,
    '__set_fields': __set_fields,
    '__set_fkeys': __set_fkeys,
    '__call__': __call__,
    '__get_set_fields': __get_set_fields,
    '__repr__': __repr__,
    '__get_from': __get_from,
    '__get_query': __get_query,
    '__fkey_where': __fkey_where,
    '__where_repr': __where_repr,
    '__where_args': __where_args,
    '__len__': __len__,

    '__set__op__': __set__op__,
    '__and__': __and__,
    '__iand__': __iand__,
    '__or__': __or__,
    '__ior__': __ior__,
    '__sub__': __sub__,
    '__isub__': __isub__,
    '__xor__': __xor__,
    '__ixor__': __ixor__,
    '__neg__': __neg__,
    '__contains__': __contains__,
    '__eq__': __eq__,

    '__sql_id': __sql_id,
    '__walk_op': __walk_op,
    '__what': __what,
    '__update_args': __update_args,
    '__add_returning': __add_returning,
    '__to_dict_val_comp': __to_dict_val_comp,
    '__enter__': __enter__,
    '__exit__': __exit__,
    '__iter__': __iter__,
    '__next__': __next__,

    # protected methods
    '_ho_freeze': _ho_freeze,
    '_ho_unfreeze': _ho_unfreeze,
    '_ho_prep_select': _ho_prep_select,
    '_ho_mogrify': _ho_mogrify,

    # public methods
    '_ho_id': _ho_id,
    '_ho_order_by': _ho_order_by,
    '_ho_limit': _ho_limit,
    '_ho_offset': _ho_offset,
    '_ho_distinct': _ho_distinct,
    '_ho_unaccent': _ho_unaccent,
    '_ho_cast': _ho_cast,
    '_ho_only': _ho_only,
    '_ho_is_empty': _ho_is_empty,
    '_ho_group_by':_ho_group_by,
    '_ho_json': _ho_json,
    '_ho_dict': _ho_dict,
    '_ho_is_set': _ho_is_set,
    '_ho_get': _ho_get,
    '_ho_join': _ho_join,
    '_ho_insert': _ho_insert,
    '_ho_select': _ho_select,
    '_ho_update': _ho_update,
    '_ho_delete': _ho_delete,

    '_ho_transaction': Transaction,
}


TABLE_INTERFACE = COMMON_INTERFACE
VIEW_INTERFACE = COMMON_INTERFACE
MVIEW_INTERFACE = COMMON_INTERFACE
FDATA_INTERFACE = COMMON_INTERFACE

REL_INTERFACES = {
    'r': TABLE_INTERFACE,
    'p': TABLE_INTERFACE,
    'v': VIEW_INTERFACE,
    'm': MVIEW_INTERFACE,
    'f': FDATA_INTERFACE}

REL_CLASS_NAMES = {
    'r': 'Table',
    'p': 'Partioned table',
    'v': 'View',
    'm': 'Materialized view',
    'f': 'Foreign data'}

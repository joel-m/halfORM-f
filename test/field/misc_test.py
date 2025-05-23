#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

from unittest import TestCase
from datetime import date

from half_orm.field import Field
from half_orm.null import NULL

from ..init import halftest

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        self.comment = halftest.comment_cls()
        self.today = halftest.today

    def tearDown(self):
        halftest.model.execute_query('alter table blog.post alter column content drop not null')
        halftest.model.reconnect(reload=True)

    def test_not_set_field(self):
        fields_set = {elt.is_set() for elt in self.pers._ho_fields.values()}
        self.assertTrue(fields_set, {False})

    def test_set_field(self):
        pers = self.pers(first_name='jojo')
        self.assertTrue(pers.first_name.is_set())

    def test_idem(self):
        pers = self.pers(first_name='jojo')
        self.assertIsInstance(pers.first_name, Field)

    def test_fields_names(self):
        field_names = set(self.pers._ho_fields.keys())
        self.assertEqual(
            field_names,
            {'id', 'first_name', 'last_name', 'birth_date'})

    def test_relation_ref(self):
        first_name = self.pers.first_name
        self.assertEqual(id(first_name._relation), id(self.pers))

    def test_unset_field_with_none(self):
        pers = self.pers(first_name='jojo')
        pers.first_name.set(None)
        self.assertEqual(pers.ho_count(), self.pers.ho_count())
        self.assertFalse(pers.first_name.is_set())

    def test_is_not_null(self):
        post = halftest.post_cls()
        self.assertFalse(post.content.is_not_null())
        halftest.model.execute_query('alter table blog.post alter column content set not null')
        halftest.model.reconnect(reload=True)
        post = halftest.post_cls()
        self.assertTrue(post.content.is_not_null())
        halftest.model.execute_query('alter table blog.post alter column content drop not null')
        halftest.model.reconnect(reload=True)

    def test_relation(self):
        post = halftest.post_cls()
        self.assertEqual(post.content._relation, halftest.post_cls())

    def test_str_value(self):
        self.post.content = 10
        self.assertEqual(str(10), str(self.post.content))
        self.post.content = ('ilike', '%10%')
        self.assertEqual('%10%', str(self.post.content))
        self.post.content = date.today()
        self.assertEqual(str(date.today()), str(self.post.content))

    def test_wrong_value(self):
        with self.assertRaises(ValueError) as exc:
            self.post.content = ('=', 'b', 'c')
        self.assertEqual("Can't match ('=', 'b', 'c') with (comp, value)!", str(exc.exception))

    def test_null_value(self):
        self.post.content = NULL
        self.assertEqual(self.post.content._comp(), 'is')
        list(self.post)

    def test_comp_is_none_error(self):
        with self.assertRaises(ValueError) as exc:
            self.post.content = ('=', None)
        self.assertEqual("Can't have a None value with a comparator!", str(exc.exception))

    def test_comp_should_be_is_error(self):
        with self.assertRaises(ValueError) as exc:
            self.post.content = ('!=', NULL)
        self.assertEqual("comp should be 'is' or 'is not' with NULL value!", str(exc.exception))

    def test_comp_pct(self):
        self.post.content = ('%', 'what ever')
        self.assertEqual('%%', str(self.post.content._comp()))

    def test_unaccent(self):
        self.assertFalse(self.post.content.unaccent)
        self.post.content.unaccent = True
        self.assertTrue(self.post.content.unaccent)

        with self.assertRaises(RuntimeError) as exc:
            self.post.content.unaccent = 'true'
        self.assertEqual("unaccent value must be True or False!", str(exc.exception))

    def test_name_property(self):
        self.assertEqual(self.post.content._name, self.post.content._Field__name)
        self.assertEqual(self.post.content._name, 'content')
        self.assertEqual(self.pers.last_name._name, 'last_name')

    def test_repr(self):
        self.assertEqual(repr(self.post.content), '(text)')
        self.assertEqual(repr(self.post.id), '(int4) NOT NULL')
        self.assertEqual(repr(self.pers.birth_date), '(date) NOT NULL')

        self.pers.birth_date = date.today()
        self.assertEqual(repr(self.pers.birth_date), f'(date) NOT NULL (birth_date = {date.today()})')

    def test_comps(self):
        self.post.content.set(['bonjour', 'au revoir'])
        self.assertIsInstance(self.post.content.value, tuple)
        self.post.content.set({'bonjour', 'au revoir'})
        self.assertIsInstance(self.post.content.value, tuple)
        self.assertEqual(self.post.content._where_repr('', id(self.post)), '"content" in %s')
        list(self.post)
        self.comment.tags.set('coucou')
        self.assertEqual(self.comment.tags._where_repr('', id(self.comment)), """%s = ANY("tags")""")
        list(self.comment)

    def test_py_type(self):
        self.assertEqual(str(self.comment.tags.py_type), 'typing.List[str]')

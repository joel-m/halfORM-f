#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import contextlib
import io
import re

import sys
from unittest import TestCase
from time import sleep
from random import randint

import psycopg2

from half_orm.hotest import HoTestCase
from half_orm import relation_errors, model

from ..init import halftest

class Test(HoTestCase):
    def setUp(self):
        self.pers = halftest.Person()
        self.post = halftest.Post()
        self.today = halftest.today
        self.blog_view = halftest.BlogView()

    def test_count(self):
        self.assertEqual(len(self.pers()), 60)

    def test_expected_one_error_0(self):
        pers = self.pers(last_name="this name doesn't exist")
        self.assertRaises(
            relation_errors.ExpectedOneError, pers.ho_get)

    def test_expected_one_error_many(self):
        pers = self.pers()
        self.assertRaises(
            relation_errors.ExpectedOneError, pers.ho_get)

    def test_insert_error(self):
        pers = self.pers(last_name='ba')
        self.assertEqual(len(pers), 1)
        pers = pers.ho_get()
        self.assertRaises(psycopg2.IntegrityError, pers.ho_insert)

    def test_select(self):
        n = 'abcdef'[randint(0, 5)]
        p = chr(ord('a') + range(10)[randint(0, 9)])
        pers = self.pers(
            last_name=('ilike', f'{n}%'),
            first_name=('ilike', f'%{p}'),
            birth_date=self.today)
        for dct in pers:
            self.pers(**dct).ho_get()

    def test_select_from_dotted_schema(self):
        "should quote dotted schema in sql request"
        list(self.blog_view)

    def test_update(self):
        pers = self.pers(last_name=('like', 'a%'))
        self.assertEqual(len(pers), 10)
        @pers.ho_transaction
        def update(pers, fct):
            for elt in pers:
                pers = self.pers.__class__(**elt)
                pers.ho_update(last_name=fct(pers.last_name.value), first_name=None)
            
        update(pers, str.upper)
        pers = self.pers(last_name=('like', 'A%'))
        self.assertEqual(len(pers), 10)
        update(pers, str.lower)

    def test_update_none_values_are_removed(self):
        "it should remove None values before update"
        self.post.ho_mogrify()
        f1 = io.StringIO()
        value1 = ''
        with contextlib.redirect_stdout(f1):
            self.pers(last_name='Un test').ho_update()
            value1 = re.sub(r'\s+', ' ', f1.getvalue().replace('\n', ' ').replace('  ', ' '))

        f2 = io.StringIO()
        value2 = ''
        with contextlib.redirect_stdout(f2):
            self.pers(last_name='Un test', first_name=None).ho_update()
            value2 = re.sub(r'\s+', ' ', f2.getvalue().replace('\n', ' ').replace('  ', ' '))
        self.assertEqual(value1, value2)

    def test_update_with_none_values(self):
        "it should return None (do nothing) if no update values are provided."
        pers = self.pers(last_name=None, first_name=None, birth_date=None)
        res = pers.ho_update(update_all=True)
        self.assertEqual(res, None)

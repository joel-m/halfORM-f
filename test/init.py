#!/usr/bin/env python3

import os
import sys
from datetime import date
from half_orm.model import Model
from half_orm.relation import singleton

path = os.path.dirname(__file__)
sys.path.insert(0, f'{path}/halftest')

README = """
Create the database halftest First:
- psql template1 -f {}/sql/halftest.sql
This command will create:
- a user halftest.
  When prompted for the password type: halftest
- a database halftest

To drop halftest database and user when you're done with the tests:
- dropdb halftest; dropuser halftest
"""

model = Model('halftest', scope="halftest")

def name(letter, integer):
    return f"{letter}{chr(ord('a') + integer)}"

class HalfTest:
    def __init__(self):
        self.model = model
        assert model._scope == "halftest"
        self.dbname = model._dbname
        self.today = date.today()
        self.Person = model._import_class("actor.person")
        class PC(self.Person):
            def last_name(self):
                pass

        self.pc = PC()
        self.pers = self.Person()
        self.relation = model._import_class
        self.post = model._import_class("blog.post")()
        self.comment = model._import_class("blog.comment")()
        self.event = model._import_class("blog.event")()
        self.blog_view = model._import_class("blog.view.post_comment")()

        @self.pers.Transaction
        def init_pers(pers):
            sys.stderr.write('Initializing actor.person\n')
            self.pers.delete(delete_all=True)
            self.post.delete(delete_all=True)
            for letter in 'abcdef':
                for i in range(10):
                    last_name = name(letter, i)
                    first_name = name(letter, i)
                    birth_date = self.today
                    pers(
                        last_name=last_name,
                        first_name=first_name,
                        birth_date=birth_date).insert()

        if len(self.pers) != 60:
            init_pers(self.pers)

halftest = HalfTest()

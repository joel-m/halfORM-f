# pylint: disable=wrong-import-order, invalid-name, attribute-defined-outside-init

"""The module halftest.actor.person povides the Person class.

WARNING!

This file is part of the halftest package. It has been generated by the
command hop. To keep it in sync with your database structure, just rerun
hop update.

More information on the half_orm library on https://github.com/collorg/halfORM.

DO NOT REMOVE OR MODIFY THE LINES BEGINING WITH:
#>>> PLACE YOUR CODE BELOW...
#<<< PLACE YOUR CODE ABOVE...

MAKE SURE YOUR CODE GOES BETWEEN THESE LINES OR AT THE END OF THE FILE.
hop ONLY PRESERVES THE CODE BETWEEN THESE MARKS WHEN IT IS RUN.
"""

from halftest.db_connector import base_relation_class

#>>> PLACE YOUR CODE BELOW THIS LINE. DO NOT REMOVE THIS LINE!
from half_orm.relation import singleton


#<<< PLACE YOUR CODE ABOVE THIS LINE. DO NOT REMOVE THIS LINE!

__RCLS = base_relation_class('actor.person')

class Person(__RCLS):
    """
    __RCLS: <class 'half_orm.model.Table_HalftestActorPerson'>
    This class allows you to manipulate the data in the PG relation:
    TABLE: "halftest":"actor"."person"
    DESCRIPTION:
    The table actor.person contains the persons of the blogging system.
    The id attribute is a serial. Just pass first_name, last_name and birth_date
    to insert a new person.
    FIELDS:
    - id:         (int4) NOT NULL
    - first_name: (text) NOT NULL
    - last_name:  (text) NOT NULL
    - birth_date: (date) NOT NULL

    PRIMARY KEY (first_name, last_name, birth_date)
    UNIQUE CONSTRAINT (id)
    UNIQUE CONSTRAINT (first_name)
    FOREIGN KEYS:
    - _reverse_fkey_halftest_blog_comment_author_id: ("id")
     ↳ "halftest":"blog"."comment"(author_id)
    - _reverse_fkey_halftest_blog_event_author_first_name_author_last_name_author_birth_date: ("birth_date", "first_name", "last_name")
     ↳ "halftest":"blog"."event"(author_first_name, author_last_name, author_birth_date)
    - _reverse_fkey_halftest_blog_post_author_first_name_author_last_name_author_birth_date: ("birth_date", "first_name", "last_name")
     ↳ "halftest":"blog"."post"(author_first_name, author_last_name, author_birth_date)

    To use the foreign keys as direct attributes of the class, copy/paste the Fkeys below into
    your code as a class attribute and replace the empty string key(s) with the alias(es) you
    want to use. The aliases must be unique and different from any of the column names. Empty
    string keys are ignored.

    Fkeys = {
        '': '_reverse_fkey_halftest_blog_comment_author_id',
        '': '_reverse_fkey_halftest_blog_event_author_first_name_author_last_name_author_birth_date',
        '': '_reverse_fkey_halftest_blog_post_author_first_name_author_last_name_author_birth_date',
    }
    """
    #>>> PLACE YOUR CODE BELOW THIS LINE. DO NOT REMOVE THIS LINE!
    Fkeys = {
        '_comment': '_reverse_fkey_halftest_blog_comment_author_id',
        '_event': '_reverse_fkey_halftest_blog_event_author_first_name_author_last_name_author_birth_date',
        '_post': '_reverse_fkey_halftest_blog_post_author_first_name_author_last_name_author_birth_date'
    }
    #<<< PLACE YOUR CODE ABOVE THIS LINE. DO NOT REMOVE THIS LINE!
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        #>>> PLACE YOUR CODE BELOW THIS LINE. DO NOT REMOVE THIS LINE!

    @singleton
    def name(self):
        """To test Relation.singleton decorator"""
        return self.last_name
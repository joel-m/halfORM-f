"""This module provides the errors for the relation module."""

class ExpectedOneError(Exception):
    """This exception is raised when get count differs from 1."""
    def __init__(self, relation, count):
        plural = '' if count == 0 else 's'
        Exception.__init__(self, 'Expected 1, got {} tuple{}:\n{}'.format(
            count, plural, relation))

import re
from functools import partial

from itertools import chain
from webargs import flaskparser, ValidationError, fields, validate

from webargs.flaskparser import use_kwargs, parser, abort
from marshmallow import EXCLUDE

# for generating swagger docs: from flask_apispec import use_kwargs
# and use its use_kwargs in "Locations" section below

"""
Helpers and partial methods to support webargs fields
"""

argsparser = flaskparser.FlaskParser()


class WebargsException(Exception):
    """
    Custom exception that can be formatted to display a nice error message,
    instead of the generic one provided by webargs.
    """

    @property
    def errors(self):
        return self.message


"""
Locations
------------------
Shorthand for setting the location to read the parameters from.
from_body = body payload (like json)
from_query = query param (i.e. ?q=<...>&m=<...>)
from_path = parameters found in URL (like /tests/<test_id>/delete)
"""
from_body = partial(use_kwargs, unknown=EXCLUDE, location="json")
from_query = partial(use_kwargs, unknown=EXCLUDE, location="querystring")
from_path = partial(use_kwargs, unknown=EXCLUDE, location='view_args')


class Validators:
    """
    Custom validators.
    Each function must be:
    1. static
    2. return False or raise a ValidationError exception when validation fails.
    """

    @staticmethod
    def non_empty_string(s):
        if s and s.strip():
            return True
        raise ValidationError("String can not be empty")

    @staticmethod
    def is_valid_id(collection, doc_id):
        """
        Check if ["_id": doc_ids] exists in collection
        :param collection: string, collection name (setups/tests/executions/...)
        :param doc_id: string, object id
        :return: raise if item not found in collection
        """
        Validators.is_valid_ids(collection, [doc_id])

    @staticmethod
    def is_valid_emails(emails_list):
        """
        Check if all emails on list are valid emails
        :param emails_list: list<Str>
        :return: raise if one of the emails on the list is not valid
        """
        for email in emails_list:
            if email != "BOTH":
                email = re.sub('[`u]', '', email)
                if not re.match("^[a-zA-Z0-9_+&*-]+(?:\\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,7}$",
                                email):
                    raise ValidationError("Invalid email address")
        return True

    class EmptyOrContainsOnly(validate.ContainsOnly):
        # Fix for "containsOnly" validation to accept empty list
        def __call__(self, value):
            if not value:
                return True
            return super(Validators.EmptyOrContainsOnly, self).__call__(value)


class Fields:
    """
    Shorthand for common fields usage.
    """

    # a required string parameter. also validates string value is not empty
    String = partial(fields.Str,
                     required=True,
                     validate=Validators.non_empty_string)

    Project = partial(fields.Str,
                      validate=Validators.non_empty_string)


    # required string field, validation that it is a Jenkins job status
    JenkinsStatus = partial(String,
                            validate=validate.OneOf(["SUCCESS", "FAILURE", "UNSTABLE", "ABORTED"],
                                                    error="Status must be one of {choices}"))

    # required string field, validation is of the form of mongo db doc id
    DocId = partial(String,
                    validate=[
                        validate.Regexp(r"^[a-f\d]{24}$",
                                        re.IGNORECASE, error="Invalid document ID")])

    StringOrNone = partial(fields.Str,
                           required=False,
                           allow_none=True,
                           missing=None)
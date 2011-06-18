"""passlib.handlers.postgres_md5 - MD5-based algorithm used by Postgres for pg_shadow table"""
#=========================================================
#imports
#=========================================================
#core
from hashlib import md5
import re
import logging; log = logging.getLogger(__name__)
from warnings import warn
#site
#libs
#pkg
from passlib.utils import handlers as uh, to_unicode, to_hash_str, bytes, b
#local
__all__ = [
    "postgres_md5",
]

#=========================================================
#handler
#=========================================================
class postgres_md5(object):
    """This class implements the Postgres MD5 Password hash, and follows the :ref:`password-hash-api`.

    It has no salt and a single fixed round.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept no optional keywords.

    The :meth:`encrypt()`, :meth:`genhash()`, and :meth:`verify()` methods all require the
    following additional contextual keywords:

    :param user: string containing name of postgres user account this password is associated with.
    """
    #=========================================================
    #algorithm information
    #=========================================================
    name = "postgres_md5"
    setting_kwds = ()
    context_kwds = ("user",)

    #=========================================================
    #formatting
    #=========================================================
    _pat = re.compile(ur"^md5[0-9a-f]{32}$")

    @classmethod
    def identify(cls, hash):
        return uh.identify_regexp(hash, cls._pat)

    #=========================================================
    #primary interface
    #=========================================================
    @classmethod
    def genconfig(cls):
        return None

    @classmethod
    def genhash(cls, secret, config, user):
        if config and not cls.identify(config):
            raise ValueError("not a postgres-md5 hash")
        return cls.encrypt(secret, user)

    #=========================================================
    #secondary interface
    #=========================================================
    @classmethod
    def encrypt(cls, secret, user):
        #FIXME: not sure what postgres' policy is for unicode
        if not user:
            raise ValueError("user keyword must be specified for this algorithm")
        if isinstance(secret, unicode):
            secret = secret.encode("utf-8")
        if isinstance(user, unicode):
            user = user.encode("utf-8")
        hash = u"md5" + to_unicode(md5(secret + user).hexdigest(), "ascii")
        return to_hash_str(hash)

    @classmethod
    def verify(cls, secret, hash, user):
        if not hash:
            raise ValueError("no hash specified")
        hash = to_hash_str(hash)
        return hash == cls.genhash(secret, hash, user)

    #=========================================================
    #eoc
    #=========================================================

#=========================================================
#eof
#=========================================================

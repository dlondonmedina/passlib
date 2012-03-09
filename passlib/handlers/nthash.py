"""passlib.handlers.nthash - unix-crypt compatible nthash passwords"""
#=========================================================
#imports
#=========================================================
#core
import re
import logging; log = logging.getLogger(__name__)
from warnings import warn
#site
#libs
from passlib.utils import to_unicode
from passlib.utils.compat import bytes, str_to_uascii, u, uascii_to_str
from passlib.utils.md4 import md4
import passlib.utils.handlers as uh
#pkg
#local
__all__ = [
    "NTHash",
]

#=========================================================
#handler
#=========================================================
class nthash(uh.HasManyIdents, uh.GenericHandler):
    """This class implements the NT Password hash in a manner compatible with the :ref:`modular-crypt-format`, and follows the :ref:`password-hash-api`.

    It has no salt and a single fixed round.

    The :meth:`encrypt()` and :meth:`genconfig` methods accept no optional keywords.
    """

    #TODO: verify where $NT$ is being used.
    ##:param ident:
    ##This handler supports two different :ref:`modular-crypt-format` identifiers.
    ##It defaults to ``3``, but users may specify the alternate ``NT`` identifier
    ##which is used in some contexts.

    #=========================================================
    #class attrs
    #=========================================================
    #--GenericHandler--
    name = "nthash"
    setting_kwds = ("ident",)
    checksum_chars = uh.LOWER_HEX_CHARS

    _stub_checksum = u("0") * 32

    #--HasManyIdents--
    default_ident = u("$3$$")
    ident_values = (u("$3$$"), u("$NT$"))
    ident_aliases = {u("3"): u("$3$$"), u("NT"): u("$NT$")}

    #=========================================================
    #formatting
    #=========================================================

    @classmethod
    def from_string(cls, hash):
        ident, chk = cls._parse_ident(hash)
        return cls(ident=ident, checksum=chk)

    def to_string(self):
        hash = self.ident + (self.checksum or self._stub_checksum)
        return uascii_to_str(hash)

    #=========================================================
    #primary interface
    #=========================================================

    def _calc_checksum(self, secret):
        return self.raw_nthash(secret, hex=True)

    @staticmethod
    def raw_nthash(secret, hex=False):
        """encode password using md4-based NTHASH algorithm

        :returns:
            returns string of raw bytes if ``hex=False``,
            returns digest as hexidecimal unicode if ``hex=True``.
        """
        secret = to_unicode(secret, "utf-8", errname="secret")
        hash = md4(secret.encode("utf-16le"))
        if hex:
            return str_to_uascii(hash.hexdigest())
        else:
            return hash.digest()

    #=========================================================
    #eoc
    #=========================================================

#=========================================================
#eof
#=========================================================

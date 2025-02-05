from binascii import hexlify


from passlib.utils import to_unicode, right_pad_string
from passlib.crypto.digest import lookup_hash

import passlib.utils.handlers as uh

md4 = lookup_hash("md4").const

__all__ = [
    "lmhash",
    "nthash",
    "bsd_nthash",
    "msdcc",
    "msdcc2",
]


class lmhash(uh.TruncateMixin, uh.HasEncodingContext, uh.StaticHandler):
    """This class implements the Lan Manager Password hash, and follows the :ref:`password-hash-api`.

    It has no salt and a single fixed round.

    The :meth:`~passlib.ifc.PasswordHash.using` method accepts a single
    optional keyword:

    :param bool truncate_error:
        By default, this will silently truncate passwords larger than 14 bytes.
        Setting ``truncate_error=True`` will cause :meth:`~passlib.ifc.PasswordHash.hash`
        to raise a :exc:`~passlib.exc.PasswordTruncateError` instead.

        .. versionadded:: 1.7

    The :meth:`~passlib.ifc.PasswordHash.hash` and :meth:`~passlib.ifc.PasswordHash.verify` methods accept a single
    optional keyword:

    :type encoding: str
    :param encoding:

        This specifies what character encoding LMHASH should use when
        calculating digest. It defaults to ``cp437``, the most
        common encoding encountered.

    Note that while this class outputs digests in lower-case hexadecimal,
    it will accept upper-case as well.
    """

    # --------------------
    # PasswordHash
    # --------------------
    name = "lmhash"
    setting_kwds = ("truncate_error",)

    # --------------------
    # GenericHandler
    # --------------------
    checksum_chars = uh.HEX_CHARS
    checksum_size = 32

    # --------------------
    # TruncateMixin
    # --------------------
    truncate_size = 14

    # --------------------
    # custom
    # --------------------
    default_encoding = "cp437"

    @classmethod
    def _norm_hash(cls, hash):
        return hash.lower()

    def _calc_checksum(self, secret):
        # check for truncation (during .hash() calls only)
        if self.use_defaults:
            self._check_truncate_policy(secret)

        return hexlify(self.raw(secret, self.encoding)).decode("ascii")

    # magic constant used by LMHASH
    _magic = b"KGS!@#$%"

    @classmethod
    def raw(cls, secret, encoding=None):
        """encode password using LANMAN hash algorithm.

        :type secret: str or utf-8 encoded bytes
        :arg secret: secret to hash
        :type encoding: str
        :arg encoding:
            optional encoding to use for unicode inputs.
            this defaults to ``cp437``, which is the
            common case for most situations.

        :returns: returns string of raw bytes
        """
        if not encoding:
            encoding = cls.default_encoding
        # some nice empircal data re: different encodings is at...
        # http://www.openwall.com/lists/john-dev/2011/08/01/2
        # http://www.freerainbowtables.com/phpBB3/viewtopic.php?t=387&p=12163
        from passlib.crypto.des import des_encrypt_block

        MAGIC = cls._magic
        if isinstance(secret, str):
            # perform uppercasing while we're still unicode,
            # to give a better shot at getting non-ascii chars right.
            # (though some codepages do NOT upper-case the same as unicode).
            secret = secret.upper().encode(encoding)
        elif isinstance(secret, bytes):
            # FIXME: just trusting ascii upper will work?
            # and if not, how to do codepage specific case conversion?
            # we could decode first using <encoding>,
            # but *that* might not always be right.
            secret = secret.upper()
        else:
            raise TypeError("secret must be str or bytes")
        secret = right_pad_string(secret, 14)
        return des_encrypt_block(secret[0:7], MAGIC) + des_encrypt_block(
            secret[7:14], MAGIC
        )


class nthash(uh.StaticHandler):
    """This class implements the NT Password hash, and follows the :ref:`password-hash-api`.

    It has no salt and a single fixed round.

    The :meth:`~passlib.ifc.PasswordHash.hash` and :meth:`~passlib.ifc.PasswordHash.genconfig` methods accept no optional keywords.

    Note that while this class outputs lower-case hexadecimal digests,
    it will accept upper-case digests as well.
    """

    name = "nthash"
    checksum_chars = uh.HEX_CHARS
    checksum_size = 32

    @classmethod
    def _norm_hash(cls, hash):
        return hash.lower()

    def _calc_checksum(self, secret):
        return hexlify(self.raw(secret)).decode("ascii")

    @classmethod
    def raw(cls, secret):
        """encode password using MD4-based NTHASH algorithm

        :arg secret: secret as unicode or utf-8 encoded bytes

        :returns: returns string of raw bytes
        """
        secret = to_unicode(secret, "utf-8", param="secret")
        # XXX: found refs that say only first 128 chars are used.
        return md4(secret.encode("utf-16-le")).digest()


bsd_nthash = uh.PrefixWrapper(
    "bsd_nthash",
    nthash,
    prefix="$3$$",
    ident="$3$$",
    doc="""The class support FreeBSD's representation of NTHASH
    (which is compatible with the :ref:`modular-crypt-format`),
    and follows the :ref:`password-hash-api`.

    It has no salt and a single fixed round.

    The :meth:`~passlib.ifc.PasswordHash.hash` and :meth:`~passlib.ifc.PasswordHash.genconfig` methods accept no optional keywords.
    """,
)


##class ntlm_pair(object):
##    "combined lmhash & nthash"
##    name = "ntlm_pair"
##    setting_kwds = ()
##    _hash_regex = re.compile(u"^(?P<lm>[0-9a-f]{32}):(?P<nt>[0-9][a-f]{32})$",
##                             re.I)
##
##    @classmethod
##    def identify(cls, hash):
##        hash = to_unicode(hash, "latin-1", "hash")
##        return len(hash) == 65 and cls._hash_regex.match(hash) is not None
##
##    @classmethod
##    def hash(cls, secret, config=None):
##        if config is not None and not cls.identify(config):
##            raise uh.exc.InvalidHashError(cls)
##        return lmhash.hash(secret) + ":" + nthash.hash(secret)
##
##    @classmethod
##    def verify(cls, secret, hash):
##        hash = to_unicode(hash, "ascii", "hash")
##        m = cls._hash_regex.match(hash)
##        if not m:
##            raise uh.exc.InvalidHashError(cls)
##        lm, nt = m.group("lm", "nt")
##        # NOTE: verify against both in case encoding issue
##        # causes one not to match.
##        return lmhash.verify(secret, lm) or nthash.verify(secret, nt)


class msdcc(uh.HasUserContext, uh.StaticHandler):
    """This class implements Microsoft's Domain Cached Credentials password hash,
    and follows the :ref:`password-hash-api`.

    It has a fixed number of rounds, and uses the associated
    username as the salt.

    The :meth:`~passlib.ifc.PasswordHash.hash`, :meth:`~passlib.ifc.PasswordHash.genhash`, and :meth:`~passlib.ifc.PasswordHash.verify` methods
    have the following optional keywords:

    :type user: str
    :param user:
        String containing name of user account this password is associated with.
        This is required to properly calculate the hash.

        This keyword is case-insensitive, and should contain just the username
        (e.g. ``Administrator``, not ``SOMEDOMAIN\\Administrator``).

    Note that while this class outputs lower-case hexadecimal digests,
    it will accept upper-case digests as well.
    """

    name = "msdcc"
    checksum_chars = uh.HEX_CHARS
    checksum_size = 32

    @classmethod
    def _norm_hash(cls, hash):
        return hash.lower()

    def _calc_checksum(self, secret):
        return hexlify(self.raw(secret, self.user)).decode("ascii")

    @classmethod
    def raw(cls, secret, user):
        """encode password using mscash v1 algorithm

        :arg secret: secret as str or utf-8 encoded bytes
        :arg user: username to use as salt

        :returns: returns string of raw bytes
        """
        secret = to_unicode(secret, "utf-8", param="secret").encode("utf-16-le")
        user = to_unicode(user, "utf-8", param="user").lower().encode("utf-16-le")
        return md4(md4(secret).digest() + user).digest()


class msdcc2(uh.HasUserContext, uh.StaticHandler):
    """This class implements version 2 of Microsoft's Domain Cached Credentials
    password hash, and follows the :ref:`password-hash-api`.

    It has a fixed number of rounds, and uses the associated
    username as the salt.

    The :meth:`~passlib.ifc.PasswordHash.hash`, :meth:`~passlib.ifc.PasswordHash.genhash`, and :meth:`~passlib.ifc.PasswordHash.verify` methods
    have the following extra keyword:

    :type user: str
    :param user:
        String containing name of user account this password is associated with.
        This is required to properly calculate the hash.

        This keyword is case-insensitive, and should contain just the username
        (e.g. ``Administrator``, not ``SOMEDOMAIN\\Administrator``).
    """

    name = "msdcc2"
    checksum_chars = uh.HEX_CHARS
    checksum_size = 32

    @classmethod
    def _norm_hash(cls, hash):
        return hash.lower()

    def _calc_checksum(self, secret):
        return hexlify(self.raw(secret, self.user)).decode("ascii")

    @classmethod
    def raw(cls, secret, user):
        """encode password using msdcc v2 algorithm

        :type secret: str or utf-8 bytes
        :arg secret: secret

        :type user: str
        :arg user: username to use as salt

        :returns: returns string of raw bytes
        """
        from passlib.crypto.digest import pbkdf2_hmac

        secret = to_unicode(secret, "utf-8", param="secret").encode("utf-16-le")
        user = to_unicode(user, "utf-8", param="user").lower().encode("utf-16-le")
        tmp = md4(md4(secret).digest() + user).digest()
        return pbkdf2_hmac("sha1", tmp, user, 10240, 16)

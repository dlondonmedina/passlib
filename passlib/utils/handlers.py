"""passlib.handler - code for implementing handlers, and global registry for handlers"""

# core
import inspect
import math
import threading
from typing import Optional, Union
from warnings import warn

from passlib import exc
from passlib import ifc
from passlib.exc import PasslibConfigWarning, PasslibHashWarning
from passlib.ifc import PasswordHash
from passlib.registry import get_crypt_handler
from passlib.utils import (
    consteq,
    getrandstr,
    getrandbytes,
    rng,
    to_unicode,
    MAX_PASSWORD_SIZE,
    accepts_keyword,
    as_bool,
    update_mixin_classes,
    join_unicode,
)
from passlib.utils.binary import (
    BASE64_CHARS,
    HASH64_CHARS,
    PADDED_BASE64_CHARS,
    HEX_CHARS,
    UPPER_HEX_CHARS,
    LOWER_HEX_CHARS,
    ALL_BYTE_VALUES,
)
from passlib.utils.compat import unicode_or_bytes
from passlib.utils.decor import classproperty, deprecated_method

# local
__all__ = [
    # helpers for implementing MCF handlers
    "parse_mc2",
    "parse_mc3",
    "render_mc2",
    "render_mc3",
    # framework for implementing handlers
    "GenericHandler",
    "StaticHandler",
    "HasUserContext",
    "HasRawChecksum",
    "HasManyIdents",
    "HasSalt",
    "HasRawSalt",
    "HasRounds",
    "HasManyBackends",
    # other helpers
    "PrefixWrapper",
    "HEX_CHARS",
    "ifc",
    # TODO: a bunch of other things are commonly assumed in this namespace
    #       (e.g. HEX_CHARS etc); need to audit uses and update this list.
]


# deprecated aliases - will be removed after passlib 1.8
H64_CHARS = HASH64_CHARS
B64_CHARS = BASE64_CHARS
PADDED_B64_CHARS = PADDED_BASE64_CHARS
UC_HEX_CHARS = UPPER_HEX_CHARS
LC_HEX_CHARS = LOWER_HEX_CHARS


def _bitsize(count, chars):
    """helper for bitsize() methods"""
    if chars and count:
        import math

        return int(count * math.log(len(chars), 2))
    else:
        return 0


def guess_app_stacklevel(start=1):
    """
    try to guess stacklevel for application warning.
    looks for first frame not part of passlib.
    """
    frame = inspect.currentframe()
    count = -start
    try:
        while frame:
            name = frame.f_globals.get("__name__", "")
            if name.startswith("tests.") or not name.startswith("passlib."):
                return max(1, count)
            count += 1
            frame = frame.f_back
        return start
    finally:
        del frame


def warn_hash_settings_deprecation(handler, kwds):
    warn(
        "passing settings to %(handler)s.hash() is deprecated, and won't be supported in Passlib 2.0; "
        "use '%(handler)s.using(**settings).hash(secret)' instead"
        % dict(handler=handler.name),
        DeprecationWarning,
        stacklevel=guess_app_stacklevel(2),
    )


def extract_settings_kwds(handler, kwds):
    """
    helper to extract settings kwds from mix of context & settings kwds.
    pops settings keys from kwds, returns them as a dict.
    """
    context_keys = set(handler.context_kwds)
    return dict((key, kwds.pop(key)) for key in list(kwds) if key not in context_keys)


_UDOLLAR = "$"
_UZERO = "0"


def validate_secret(secret):
    """ensure secret has correct type & size"""
    if not isinstance(secret, unicode_or_bytes):
        raise exc.ExpectedStringError(secret, "secret")
    if len(secret) > MAX_PASSWORD_SIZE:
        raise exc.PasswordSizeError(MAX_PASSWORD_SIZE)


def to_unicode_for_identify(hash):
    """convert hash to unicode for identify method"""
    if isinstance(hash, str):
        return hash
    elif isinstance(hash, bytes):
        # try as utf-8, but if it fails, use foolproof latin-1,
        # since we don't really care about non-ascii chars
        # when running identify.
        try:
            return hash.decode("utf-8")
        except UnicodeDecodeError:
            return hash.decode("latin-1")
    else:
        raise exc.ExpectedStringError(hash, "hash")


def parse_mc2(hash, prefix, sep=_UDOLLAR, handler=None):
    """parse hash using 2-part modular crypt format.

    this expects a hash of the format :samp:`{prefix}{salt}[${checksum}]`,
    such as md5_crypt, and parses it into salt / checksum portions.

    :arg hash: the hash to parse (bytes or str)
    :arg prefix: the identifying prefix (str)
    :param sep: field separator (unicode, defaults to ``$``).
    :param handler: handler class to pass to error constructors.

    :returns:
        a ``(salt, chk | None)`` tuple.
    """
    # detect prefix
    hash = to_unicode(hash, "ascii", "hash")
    assert isinstance(prefix, str)
    if not hash.startswith(prefix):
        raise exc.InvalidHashError(handler)

    # parse 2-part hash or 1-part config string
    assert isinstance(sep, str)
    parts = hash[len(prefix) :].split(sep)
    if len(parts) == 2:
        salt, chk = parts
        return salt, chk or None
    elif len(parts) == 1:
        return parts[0], None
    else:
        raise exc.MalformedHashError(handler)


def parse_mc3(
    hash, prefix, sep=_UDOLLAR, rounds_base=10, default_rounds=None, handler=None
):
    """parse hash using 3-part modular crypt format.

    this expects a hash of the format :samp:`{prefix}[{rounds}]${salt}[${checksum}]`,
    such as sha1_crypt, and parses it into rounds / salt / checksum portions.
    tries to convert the rounds to an integer,
    and throws error if it has zero-padding.

    :arg hash: the hash to parse (bytes or unicode)
    :arg prefix: the identifying prefix (unicode)
    :param sep: field separator (unicode, defaults to ``$``).
    :param rounds_base:
        the numeric base the rounds are encoded in (defaults to base 10).
    :param default_rounds:
        the default rounds value to return if the rounds field was omitted.
        if this is ``None`` (the default), the rounds field is *required*.
    :param handler: handler class to pass to error constructors.

    :returns:
        a ``(rounds : int, salt, chk | None)`` tuple.
    """
    # detect prefix
    hash = to_unicode(hash, "ascii", "hash")
    assert isinstance(prefix, str)
    if not hash.startswith(prefix):
        raise exc.InvalidHashError(handler)

    # parse 3-part hash or 2-part config string
    assert isinstance(sep, str)
    parts = hash[len(prefix) :].split(sep)
    if len(parts) == 3:
        rounds, salt, chk = parts
    elif len(parts) == 2:
        rounds, salt = parts
        chk = None
    else:
        raise exc.MalformedHashError(handler)

    # validate & parse rounds portion
    if rounds.startswith(_UZERO) and rounds != _UZERO:
        raise exc.ZeroPaddedRoundsError(handler)
    elif rounds:
        rounds = int(rounds, rounds_base)
    elif default_rounds is None:
        raise exc.MalformedHashError(handler, "empty rounds field")
    else:
        rounds = default_rounds

    # return result
    return rounds, salt, chk or None


# def parse_mc3_long(hash, prefix, sep=_UDOLLAR, handler=None):
#     """
#     parse hash using 3-part modular crypt format,
#     with complex settings string instead of simple rounds.
#     otherwise works same as :func:`parse_mc3`
#     """
#     # detect prefix
#     hash = to_unicode(hash, "ascii", "hash")
#     assert isinstance(prefix, unicode)
#     if not hash.startswith(prefix):
#         raise exc.InvalidHashError(handler)
#
#     # parse 3-part hash or 2-part config string
#     assert isinstance(sep, unicode)
#     parts = hash[len(prefix):].split(sep)
#     if len(parts) == 3:
#         return parts
#     elif len(parts) == 2:
#         settings, salt = parts
#         return settings, salt, None
#     else:
#         raise exc.MalformedHashError(handler)


def parse_int(source, base=10, default=None, param="value", handler=None):
    """
    helper to parse an integer config field

    :arg source: unicode source string
    :param base: numeric base
    :param default: optional default if source is empty
    :param param: name of variable, for error msgs
    :param handler: handler class, for error msgs
    """
    if source.startswith(_UZERO) and source != _UZERO:
        raise exc.MalformedHashError(handler, "zero-padded %s field" % param)
    elif source:
        return int(source, base)
    elif default is None:
        raise exc.MalformedHashError(handler, "empty %s field" % param)
    else:
        return default


def render_mc2(ident, salt, checksum, sep="$"):
    """format hash using 2-part modular crypt format; inverse of parse_mc2()

    returns native string with format :samp:`{ident}{salt}[${checksum}]`,
    such as used by md5_crypt.

    :arg ident: identifier prefix (unicode)
    :arg salt: encoded salt (unicode)
    :arg checksum: encoded checksum (unicode or None)
    :param sep: separator char (unicode, defaults to ``$``)

    :returns:
        config or hash (native str)
    """
    if checksum:
        parts = [ident, salt, sep, checksum]
    else:
        parts = [ident, salt]
    return "".join(parts)


def render_mc3(ident, rounds, salt, checksum, sep="$", rounds_base=10):
    """format hash using 3-part modular crypt format; inverse of parse_mc3()

    returns native string with format :samp:`{ident}[{rounds}$]{salt}[${checksum}]`,
    such as used by sha1_crypt.

    :arg ident: identifier prefix (unicode)
    :arg rounds: rounds field (int or None)
    :arg salt: encoded salt (unicode)
    :arg checksum: encoded checksum (unicode or None)
    :param sep: separator char (unicode, defaults to ``$``)
    :param rounds_base: base to encode rounds value (defaults to base 10)

    :returns:
        config or hash (native str)
    """
    if rounds is None:
        rounds = ""
    elif rounds_base == 16:
        rounds = "%x" % rounds
    else:
        assert rounds_base == 10
        rounds = str(rounds)
    if checksum:
        parts = [ident, rounds, sep, salt, sep, checksum]
    else:
        parts = [ident, rounds, sep, salt]
    return join_unicode(parts)


def mask_value(value, show=4, pct=0.125, char="*"):
    """
    helper to mask contents of sensitive field.

    :param value:
        raw value (str, bytes, etc)

    :param show:
        max # of characters to remain visible

    :param pct:
        don't show more than this % of input.

    :param char:
        character to use for masking

    :rtype: str | None
    """
    if value is None:
        return None
    if not isinstance(value, str):
        if isinstance(value, bytes):
            from passlib.utils.binary import ab64_encode

            value = ab64_encode(value).decode("ascii")
        else:
            value = str(value)
    size = len(value)
    show = min(show, int(size * pct))
    return value[:show] + char * (size - show)


def validate_default_value(handler, default, norm, param="value"):
    """
    assert helper that quickly validates default value.
    designed to get out of the way and reduce overhead when asserts are stripped.
    """
    assert default is not None, "%s lacks default %s" % (handler.name, param)
    assert norm(default) == default, "%s: invalid default %s: %r" % (
        handler.name,
        param,
        default,
    )
    return True


def norm_integer(
    handler,
    value,
    min=1,
    max=None,  # *
    param="value",
    relaxed=False,
):
    """
    helper to normalize and validate an integer value (e.g. rounds, salt_size)

    :arg value: value provided to constructor
    :arg default: default value if none provided. if set to ``None``, value is required.
    :arg param: name of parameter (xxx: move to first arg?)
    :param min: minimum value (defaults to 1)
    :param max: maximum value (default ``None`` means no maximum)
    :returns: validated value
    """
    # check type
    if not isinstance(value, int):
        raise exc.ExpectedTypeError(value, "integer", param)

    # check minimum
    if value < min:
        msg = "%s: %s (%d) is too low, must be at least %d" % (
            handler.name,
            param,
            value,
            min,
        )
        if relaxed:
            warn(msg, exc.PasslibHashWarning)
            value = min
        else:
            raise ValueError(msg)

    # check maximum
    if max and value > max:
        msg = "%s: %s (%d) is too large, cannot be more than %d" % (
            handler.name,
            param,
            value,
            max,
        )
        if relaxed:
            warn(msg, exc.PasslibHashWarning)
            value = max
        else:
            raise ValueError(msg)

    return value


class MinimalHandler(PasswordHash):
    """
    helper class for implementing hash handlers.
    provides nothing besides a base implementation of the .using() subclass constructor.
    """

    #: private flag used by using() constructor to detect if this is already a subclass.
    _configured = False

    @classmethod
    def using(cls, relaxed=False):
        # NOTE: this provides the base implementation, which takes care of
        #       creating the newly configured class. Mixins and subclasses
        #       should wrap this, and modify the returned class to suit their options.
        # NOTE: 'relaxed' keyword is ignored here, but parsed so that subclasses
        #       can check for it as argument, and modify their parsing behavior accordingly.
        name = cls.__name__
        if not cls._configured:
            # TODO: straighten out class naming, repr, and .name attr
            name = "<customized %s hasher>" % name
        return type(name, (cls,), dict(__module__=cls.__module__, _configured=True))


class TruncateMixin(MinimalHandler):
    """
    PasswordHash mixin which provides a method
    that will check if secret would be truncated,
    and can be configured to throw an error.

    .. warning::

        Hashers using this mixin will generally need to override
        the default PasswordHash.truncate_error policy of "True",
        and will similarly want to override .truncate_verify_reject as well.

        TODO: This should be done explicitly, but for now this mixin sets
        these flags implicitly.
    """

    truncate_error = False
    truncate_verify_reject = False

    @classmethod
    def using(cls, truncate_error=None, **kwds):
        subcls = super().using(**kwds)
        if truncate_error is not None:
            truncate_error = as_bool(truncate_error, param="truncate_error")
            if truncate_error is not None:
                subcls.truncate_error = truncate_error
        return subcls

    @classmethod
    def _check_truncate_policy(cls, secret):
        """
        make sure secret won't be truncated.
        NOTE: this should only be called for .hash(), not for .verify(),
        which should honor the .truncate_verify_reject policy.
        """
        assert cls.truncate_size is not None, "truncate_size must be set by subclass"
        if cls.truncate_error and len(secret) > cls.truncate_size:
            raise exc.PasswordTruncateError(cls)


class GenericHandler(MinimalHandler):
    """helper class for implementing hash handlers.

    GenericHandler-derived classes will have (at least) the following
    constructor options, though others may be added by mixins
    and by the class itself:

    :param checksum:
        this should contain the digest portion of a
        parsed hash (mainly provided when the constructor is called
        by :meth:`from_string()`).
        defaults to ``None``.

    :param use_defaults:
        If ``False`` (the default), a :exc:`TypeError` should be thrown
        if any settings required by the handler were not explicitly provided.

        If ``True``, the handler should attempt to provide a default for any
        missing values. This means generate missing salts, fill in default
        cost parameters, etc.

        This is typically only set to ``True`` when the constructor
        is called by :meth:`hash`, allowing user-provided values
        to be handled in a more permissive manner.

    :param relaxed:
        If ``False`` (the default), a :exc:`ValueError` should be thrown
        if any settings are out of bounds or otherwise invalid.

        If ``True``, they should be corrected if possible, and a warning
        issue. If not possible, only then should an error be raised.
        (e.g. under ``relaxed=True``, rounds values will be clamped
        to min/max rounds).

        This is mainly used when parsing the config strings of certain
        hashes, whose specifications implementations to be tolerant
        of incorrect values in salt strings.

    Class Attributes
    ================

    .. attribute:: ident

        [optional]
        If this attribute is filled in, the default :meth:`identify` method will use
        it as a identifying prefix that can be used to recognize instances of this handler's
        hash. Filling this out is recommended for speed.

        This should be a unicode str.

    .. attribute:: _hash_regex

        [optional]
        If this attribute is filled in, the default :meth:`identify` method
        will use it to recognize instances of the hash. If :attr:`ident`
        is specified, this will be ignored.

        This should be a unique regex object.

    .. attribute:: checksum_size

        [optional]
        Specifies the number of characters that should be expected in the checksum string.
        If omitted, no check will be performed.

    .. attribute:: checksum_chars

        [optional]
        A string listing all the characters allowed in the checksum string.
        If omitted, no check will be performed.

        This should be a unicode str.

    .. attribute:: _stub_checksum

        Placeholder checksum that will be used by genconfig()
        in lieu of actually generating a hash for the empty string.
        This should be a string of the same datatype as :attr:`checksum`.

    Instance Attributes
    ===================
    .. attribute:: checksum

        The checksum string provided to the constructor (after passing it
        through :meth:`_norm_checksum`).

    Required Subclass Methods
    =========================
    The following methods must be provided by handler subclass:

    .. automethod:: from_string
    .. automethod:: to_string
    .. automethod:: _calc_checksum

    Default Methods
    ===============
    The following methods have default implementations that should work for
    most cases, though they may be overridden if the hash subclass needs to:

    .. automethod:: _norm_checksum

    .. automethod:: genconfig
    .. automethod:: genhash
    .. automethod:: identify
    .. automethod:: hash
    .. automethod:: verify
    """

    # this must be provided by the actual class.
    setting_kwds: Optional[tuple[str, ...]] = None

    # providing default since most classes don't use this at all.
    context_kwds: tuple[str, ...] = ()

    # optional prefix that uniquely identifies hash
    ident: Optional[str] = None

    # optional regexp for recognizing hashes,
    # used by default identify() if .ident isn't specified.
    _hash_regex = None

    # if specified, _norm_checksum will require this length
    checksum_size: Optional[int] = None

    # if specified, _norm_checksum() will validate this
    checksum_chars: Optional[str] = None

    # private flag used by HasRawChecksum
    _checksum_is_bytes = False
    checksum = None  # stores checksum

    #    use_defaults = False # whether _norm_xxx() funcs should fill in defaults.
    #    relaxed = False # when _norm_xxx() funcs should be strict about inputs
    def __init__(self, checksum=None, use_defaults=False, **kwds):
        self.use_defaults = use_defaults
        super().__init__(**kwds)
        if checksum is not None:
            # XXX: do we need to set .relaxed for checksum coercion?
            self.checksum = self._norm_checksum(checksum)

    # NOTE: would like to make this classmethod, but fshp checksum size
    #       is dependant on .variant, so leaving this as instance method.
    def _norm_checksum(self, checksum, relaxed=False):
        """validates checksum keyword against class requirements,
        returns normalized version of checksum.
        """
        # NOTE: by default this code assumes checksum should be unicode.
        # For classes where the checksum is raw bytes, the HasRawChecksum sets
        # the _checksum_is_bytes flag which alters various code paths below.

        # normalize to bytes / unicode
        raw = self._checksum_is_bytes
        if raw:
            # NOTE: no clear route to reasonably convert unicode -> raw bytes,
            #       so 'relaxed' does nothing here
            if not isinstance(checksum, bytes):
                raise exc.ExpectedTypeError(checksum, "bytes", "checksum")

        elif not isinstance(checksum, str):
            if isinstance(checksum, bytes) and relaxed:
                warn("checksum should be unicode, not bytes", PasslibHashWarning)
                checksum = checksum.decode("ascii")
            else:
                raise exc.ExpectedTypeError(checksum, "str", "checksum")

        # check size
        cc = self.checksum_size
        if cc and len(checksum) != cc:
            raise exc.ChecksumSizeError(self, raw=raw)

        # check charset
        if not raw:
            cs = self.checksum_chars
            if cs and any(c not in cs for c in checksum):
                raise ValueError("invalid characters in %s checksum" % (self.name,))

        return checksum

    @classmethod
    def identify(cls, hash):
        # NOTE: subclasses may wish to use faster / simpler identify,
        # and raise value errors only when an invalid (but identifiable)
        # string is parsed
        hash = to_unicode_for_identify(hash)
        if not hash:
            return False

        # does class specify a known unique prefix to look for?
        ident = cls.ident
        if ident is not None:
            return hash.startswith(ident)

        # does class provide a regexp to use?
        pat = cls._hash_regex
        if pat is not None:
            return pat.match(hash) is not None

        # as fallback, try to parse hash, and see if we succeed.
        # inefficient, but works for most cases.
        try:
            cls.from_string(hash)
            return True
        except ValueError:
            return False

    @classmethod
    def from_string(cls, hash, **context):  # pragma: no cover
        r"""
        return parsed instance from hash/configuration string

        :param \\*\\*context:
            context keywords to pass to constructor (if applicable).

        :raises ValueError: if hash is incorrectly formatted

        :returns:
            hash parsed into components,
            for formatting / calculating checksum.
        """
        raise NotImplementedError("%s must implement from_string()" % (cls,))

    def to_string(self):  # pragma: no cover
        """render instance to hash or configuration string

        :returns:
            hash string with salt & digest included.

            should return native str.
        """
        raise NotImplementedError("%s must implement from_string()" % (self.__class__,))

    # NOTE: this is only used by genconfig(), and will be removed in passlib 2.0
    @property
    def _stub_checksum(self):
        """
        placeholder used by default .genconfig() so it can avoid expense of calculating digest.
        """
        # used fixed string if available
        if self.checksum_size:
            if self._checksum_is_bytes:
                return b"\x00" * self.checksum_size
            if self.checksum_chars:
                return self.checksum_chars[0] * self.checksum_size

        # hack to minimize cost of calculating real checksum
        if isinstance(self, HasRounds):
            orig = self.rounds
            self.rounds = self.min_rounds or 1
            try:
                return self._calc_checksum("")
            finally:
                self.rounds = orig

        # final fallback, generate a real checksum
        return self._calc_checksum("")

    def _calc_checksum(self, secret):  # pragma: no cover
        """given secret; calcuate and return encoded checksum portion of hash
        string, taking config from object state

        calc checksum implementations may assume secret is always
        either str or bytes, checks are performed by verify/etc.
        """
        raise NotImplementedError(
            "%s must implement _calc_checksum()" % (self.__class__,)
        )

    @classmethod
    def hash(cls, secret, **kwds):
        if kwds:
            # Deprecating passing any settings keywords via .hash() as of passlib 1.7; everything
            # should use .using().hash() instead.  If any keywords are specified, presume they're
            # context keywords by default (the common case), and extract out any settings kwds.
            # Support for passing settings via .hash() will be removed in Passlib 2.0, along with
            # this block of code.
            settings = extract_settings_kwds(cls, kwds)
            if settings:
                warn_hash_settings_deprecation(cls, settings)
                return cls.using(**settings).hash(secret, **kwds)
        # NOTE: at this point, 'kwds' should just contain context_kwds subset
        validate_secret(secret)
        self = cls(use_defaults=True, **kwds)
        self.checksum = self._calc_checksum(secret)
        return self.to_string()

    @classmethod
    def verify(cls, secret, hash, **context):
        # NOTE: classes with multiple checksum encodings should either
        # override this method, or ensure that from_string() / _norm_checksum()
        # ensures .checksum always uses a single canonical representation.
        validate_secret(secret)
        self = cls.from_string(hash, **context)
        chk = self.checksum
        if chk is None:
            raise exc.MissingDigestError(cls)
        return consteq(self._calc_checksum(secret), chk)

    @deprecated_method(deprecated="1.7", removed="2.0")
    @classmethod
    def genconfig(cls, **kwds):
        # NOTE: 'kwds' should generally always be settings, so after this completes, *should* be empty.
        settings = extract_settings_kwds(cls, kwds)
        if settings:
            return cls.using(**settings).genconfig(**kwds)
        # NOTE: this uses optional stub checksum to bypass potentially expensive digest generation,
        #       when caller just wants the config string.
        self = cls(use_defaults=True, **kwds)
        self.checksum = self._stub_checksum
        return self.to_string()

    @deprecated_method(deprecated="1.7", removed="2.0")
    @classmethod
    def genhash(cls, secret, config, **context):
        if config is None:
            raise TypeError("config must be string")
        validate_secret(secret)
        self = cls.from_string(config, **context)
        self.checksum = self._calc_checksum(secret)
        return self.to_string()

    @classmethod
    def needs_update(cls, hash, secret=None, **kwds):
        # NOTE: subclasses should generally just wrap _calc_needs_update()
        #       to check their particular keywords.
        self = cls.from_string(hash)
        assert isinstance(self, cls)
        return self._calc_needs_update(secret=secret, **kwds)

    def _calc_needs_update(self, secret=None):
        """
        internal helper for :meth:`needs_update`.
        """
        # NOTE: this just provides a stub, subclasses & mixins
        #       should override this with their own tests.
        return False

    # ===================================================================
    # experimental - the following methods are not finished or tested,
    # but way work correctly for some hashes
    # ===================================================================

    #: internal helper for forcing settings to be included, even if default matches
    _always_parse_settings = ()

    #: internal helper for excluding certain setting_kwds from parsehash() result
    _unparsed_settings = ("salt_size", "relaxed")

    #: parsehash() keys that need to be sanitized
    _unsafe_settings = ("salt", "checksum")

    @classproperty
    def _parsed_settings(cls):
        """
        helper for :meth:`parsehash` --
        returns list of attributes which should be extracted by parse_hash() from hasher object.

        default implementation just takes setting_kwds, and excludes _unparsed_settings
        """
        return tuple(
            key for key in cls.setting_kwds if key not in cls._unparsed_settings
        )

    @classmethod
    def parsehash(cls, hash, checksum=True, sanitize=False):
        """[experimental method] parse hash into dictionary of settings.

        this essentially acts as the inverse of :meth:`hash`: for most
        cases, if ``hash = cls.hash(secret, **opts)``, then
        ``cls.parsehash(hash)`` will return a dict matching the original options
        (with the extra keyword *checksum*).

        this method may not work correctly for all hashes,
        and may not be available on some few. its interface may
        change in future releases, if it's kept around at all.

        :arg hash: hash to parse
        :param checksum: include checksum keyword? (defaults to True)
        :param sanitize: mask data for sensitive fields? (defaults to False)
        """
        # FIXME: this may not work for hashes with non-standard settings.
        # XXX: how should this handle checksum/salt encoding?
        # need to work that out for hash() anyways.
        self = cls.from_string(hash)
        # XXX: could split next few lines out as self._parsehash() for subclassing
        # XXX: could try to resolve ident/variant to publically suitable alias.
        # XXX: for v1.8, consider making "always" the default policy, and compare to class default
        #      only for whitelisted attrs? or make this whole method obsolete by reworking
        #      so "hasher" object & it's attrs are public?
        UNSET = object()
        always = self._always_parse_settings
        kwds = dict(
            (key, getattr(self, key))
            for key in self._parsed_settings
            if key in always or getattr(self, key) != getattr(cls, key, UNSET)
        )
        if checksum and self.checksum is not None:
            kwds["checksum"] = self.checksum
        if sanitize:
            if sanitize is True:
                sanitize = mask_value
            for key in cls._unsafe_settings:
                if key in kwds:
                    kwds[key] = sanitize(kwds[key])
        return kwds

    @classmethod
    def bitsize(cls, **kwds):
        """[experimental method] return info about bitsizes of hash"""
        try:
            info = super().bitsize(**kwds)
        except AttributeError:
            info = {}
        cc = ALL_BYTE_VALUES if cls._checksum_is_bytes else cls.checksum_chars
        if cls.checksum_size and cc:
            # FIXME: this may overestimate size due to padding bits (e.g. bcrypt)
            # FIXME: this will be off by 1 for case-insensitive hashes.
            info["checksum"] = _bitsize(cls.checksum_size, cc)
        return info


class StaticHandler(GenericHandler):
    """GenericHandler mixin for classes which have no settings.

    This mixin assumes the entirety of the hash ise stored in the
    :attr:`checksum` attribute; that the hash has no rounds, salt,
    etc. This class provides the following:

    * a default :meth:`genconfig` that always returns None.
    * a default :meth:`from_string` and :meth:`to_string`
      that store the entire hash within :attr:`checksum`,
      after optionally stripping a constant prefix.

    All that is required by subclasses is an implementation of
    the :meth:`_calc_checksum` method.
    """

    # TODO: document _norm_hash()

    setting_kwds = ()

    # optional constant prefix subclasses can specify
    _hash_prefix = ""

    @classmethod
    def from_string(cls, hash, **context):
        # default from_string() which strips optional prefix,
        # and passes rest unchanged as checksum value.
        hash = to_unicode(hash, "ascii", "hash")
        hash = cls._norm_hash(hash)
        # could enable this for extra strictness
        ##pat = cls._hash_regex
        ##if pat and pat.match(hash) is None:
        ##    raise ValueError("not a valid %s hash" % (cls.name,))
        prefix = cls._hash_prefix
        if prefix:
            if hash.startswith(prefix):
                hash = hash[len(prefix) :]
            else:
                raise exc.InvalidHashError(cls)
        return cls(checksum=hash, **context)

    @classmethod
    def _norm_hash(cls, hash):
        """helper for subclasses to normalize case if needed"""
        return hash

    def to_string(self):
        return self._hash_prefix + self.checksum


class HasEncodingContext(GenericHandler):
    """helper for classes which require knowledge of the encoding used"""

    context_kwds = ("encoding",)
    default_encoding = "utf-8"

    def __init__(self, encoding=None, **kwds):
        super().__init__(**kwds)
        self.encoding = encoding or self.default_encoding


class HasUserContext(GenericHandler):
    """helper for classes which require a user context keyword"""

    context_kwds = ("user",)

    def __init__(self, user=None, **kwds):
        super().__init__(**kwds)
        self.user = user

    # XXX: would like to validate user input here, but calls to from_string()
    # which lack context keywords would then fail; so leaving code per-handler.

    # wrap funcs to accept 'user' as positional arg for ease of use.
    @classmethod
    def hash(cls, secret, user=None, **context):
        return super().hash(secret, user=user, **context)

    @classmethod
    def verify(cls, secret, hash, user=None, **context):
        return super().verify(secret, hash, user=user, **context)

    @deprecated_method(deprecated="1.7", removed="2.0")
    @classmethod
    def genhash(cls, secret, config, user=None, **context):
        return super().genhash(secret, config, user=user, **context)

    # XXX: how to guess the entropy of a username?
    #      most of these hashes are for a system (e.g. Oracle)
    #      which has a few *very common* names and thus really low entropy;
    #      while the rest are slightly less predictable.
    #      need to find good reference about this.
    ##@classmethod
    ##def bitsize(cls, **kwds):
    ##    info = super().bitsize(**kwds)
    ##    info['user'] = xxx
    ##    return info


class HasRawChecksum(GenericHandler):
    """mixin for classes which work with decoded checksum bytes

    .. todo::

        document this class's usage
    """

    # NOTE: GenericHandler.checksum_chars is ignored by this implementation.

    # NOTE: all HasRawChecksum code is currently part of GenericHandler,
    # using private '_checksum_is_bytes' flag.
    # this arrangement may be changed in the future.
    _checksum_is_bytes = True


class HasManyIdents(GenericHandler):
    """mixin for hashes which use multiple prefix identifiers

    For the hashes which may use multiple identifier prefixes,
    this mixin adds an ``ident`` keyword to constructor.
    Any value provided is passed through the :meth:`norm_idents` method,
    which takes care of validating the identifier,
    as well as allowing aliases for easier specification
    of the identifiers by the user.

    .. todo::

        document this class's usage

    Class Methods
    =============
    .. todo:: document using() and needs_update() options
    """

    default_ident = None  # should be str
    ident_values = None  # should be list of unicode strings
    ident_aliases = None  # should be dict of unicode -> unicode
    # NOTE: any aliases provided to norm_ident() as bytes
    #       will have been converted to unicode before
    #       comparing against this dictionary.

    # NOTE: relying on test_06_HasManyIdents() to verify
    #       these are configured correctly.
    ident = None

    @classmethod
    def using(
        cls,  # keyword only...
        default_ident=None,
        ident=None,
        **kwds,
    ):
        """
        This mixin adds support for the following :meth:`~passlib.ifc.PasswordHash.using` keywords:

        :param default_ident:
            default identifier that will be used by resulting customized hasher.

        :param ident:
            supported as alternate alias for **default_ident**.
        """
        # resolve aliases
        if ident is not None:
            if default_ident is not None:
                raise TypeError("'default_ident' and 'ident' are mutually exclusive")
            default_ident = ident

        # create subclass
        subcls = super().using(**kwds)

        # add custom default ident
        # (NOTE: creates instance to run value through _norm_ident())
        if default_ident is not None:
            subcls.default_ident = cls(ident=default_ident, use_defaults=True).ident
        return subcls

    def __init__(self, ident=None, **kwds):
        super().__init__(**kwds)

        # init ident
        if ident is not None:
            ident = self._norm_ident(ident)
        elif self.use_defaults:
            ident = self.default_ident
            assert validate_default_value(
                self, ident, self._norm_ident, param="default_ident"
            )
        else:
            raise TypeError("no ident specified")
        self.ident = ident

    @classmethod
    def _norm_ident(cls, ident):
        """
        helper which normalizes & validates 'ident' value.
        """
        # handle bytes
        assert ident is not None
        if isinstance(ident, bytes):
            ident = ident.decode("ascii")

        # check if identifier is valid
        iv = cls.ident_values
        if ident in iv:
            return ident

        # resolve aliases, and recheck against ident_values
        ia = cls.ident_aliases
        if ia:
            try:
                value = ia[ident]
            except KeyError:
                pass
            else:
                if value in iv:
                    return value

        # failure!
        # XXX: give this it's own error type?
        raise ValueError("invalid ident: %r" % (ident,))

    @classmethod
    def identify(cls, hash):
        hash = to_unicode_for_identify(hash)
        return hash.startswith(cls.ident_values)

    @classmethod
    def _parse_ident(cls, hash):
        """extract ident prefix from hash, helper for subclasses' from_string()"""
        hash = to_unicode(hash, "ascii", "hash")
        for ident in cls.ident_values:
            if hash.startswith(ident):
                return ident, hash[len(ident) :]
        raise exc.InvalidHashError(cls)

    # XXX: implement a needs_update() helper that marks everything but default_ident as deprecated?


class HasSalt(GenericHandler):
    """mixin for validating salts.

    This :class:`GenericHandler` mixin adds a ``salt`` keyword to the class constuctor;
    any value provided is passed through the :meth:`_norm_salt` method,
    which takes care of validating salt length and content,
    as well as generating new salts if one it not provided.

    :param salt:
        optional salt string

    :param salt_size:
        optional size of salt (only used if no salt provided);
        defaults to :attr:`default_salt_size`.

    Class Attributes
    ================
    In order for :meth:`!_norm_salt` to do its job, the following
    attributes should be provided by the handler subclass:

    .. attribute:: min_salt_size

        The minimum number of characters allowed in a salt string.
        An :exc:`ValueError` will be throw if the provided salt is too small.
        Defaults to ``0``.

    .. attribute:: max_salt_size

        The maximum number of characters allowed in a salt string.
        By default an :exc:`ValueError` will be throw if the provided salt is
        too large; but if ``relaxed=True``, it will be clipped and a warning
        issued instead. Defaults to ``None``, for no maximum.

    .. attribute:: default_salt_size

        [required]
        If no salt is provided, this should specify the size of the salt
        that will be generated by :meth:`_generate_salt`. By default
        this will fall back to :attr:`max_salt_size`.

    .. attribute:: salt_chars

        A string containing all the characters which are allowed in the salt
        string. An :exc:`ValueError` will be throw if any other characters
        are encountered. May be set to ``None`` to skip this check (but see
        in :attr:`default_salt_chars`).

    .. attribute:: default_salt_chars

        [required]
        This attribute controls the set of characters use to generate
        *new* salt strings. By default, it mirrors :attr:`salt_chars`.
        If :attr:`!salt_chars` is ``None``, this attribute must be specified
        in order to generate new salts. Aside from that purpose,
        the main use of this attribute is for hashes which wish to generate
        salts from a restricted subset of :attr:`!salt_chars`; such as
        accepting all characters, but only using a-z.

    Instance Attributes
    ===================
    .. attribute:: salt

        This instance attribute will be filled in with the salt provided
        to the constructor (as adapted by :meth:`_norm_salt`)

    Subclassable Methods
    ====================
    .. automethod:: _norm_salt
    .. automethod:: _generate_salt
    """

    # TODO: document _truncate_salt()
    # XXX: allow providing raw salt to this class, and encoding it?

    min_salt_size = 0
    max_salt_size: Optional[int] = None
    salt_chars: Optional[str] = None

    @classproperty
    def default_salt_size(cls):
        """default salt size (defaults to *max_salt_size*)"""
        return cls.max_salt_size

    @classproperty
    def default_salt_chars(cls):
        """charset used to generate new salt strings (defaults to *salt_chars*)"""
        return cls.salt_chars

    # private helpers for HasRawSalt, shouldn't be used by subclasses
    _salt_is_bytes = False
    _salt_unit = "chars"

    # TODO: could support using(min/max_desired_salt_size) via using() and needs_update()
    salt = None

    @classmethod
    def using(
        cls,  # keyword only...
        default_salt_size=None,
        salt_size=None,  # aliases used by CryptContext
        salt=None,
        **kwds,
    ):
        # check for aliases used by CryptContext
        if salt_size is not None:
            if default_salt_size is not None:
                raise TypeError(
                    "'salt_size' and 'default_salt_size' aliases are mutually exclusive"
                )
            default_salt_size = salt_size

        # generate new subclass
        subcls = super().using(**kwds)

        # replace default_rounds
        relaxed = kwds.get("relaxed")
        if default_salt_size is not None:
            if isinstance(default_salt_size, str):
                default_salt_size = int(default_salt_size)
            subcls.default_salt_size = subcls._clip_to_valid_salt_size(
                default_salt_size, param="salt_size", relaxed=relaxed
            )

        # if salt specified, replace _generate_salt() with fixed output.
        # NOTE: this is mainly useful for testing / debugging.
        if salt is not None:
            salt = subcls._norm_salt(salt, relaxed=relaxed)
            subcls._generate_salt = staticmethod(lambda: salt)

        return subcls

    # XXX: would like to combine w/ _norm_salt() code below, but doesn't quite fit.
    @classmethod
    def _clip_to_valid_salt_size(cls, salt_size, param="salt_size", relaxed=True):
        """
        internal helper --
        clip salt size value to handler's absolute limits (min_salt_size / max_salt_size)

        :param relaxed:
            if ``True`` (the default), issues PasslibHashWarning is rounds are outside allowed range.
            if ``False``, raises a ValueError instead.

        :param param:
            optional name of parameter to insert into error/warning messages.

        :returns:
            clipped rounds value
        """
        mn = cls.min_salt_size
        mx = cls.max_salt_size

        # check if salt size is fixed
        if mn == mx:
            if salt_size != mn:
                msg = "%s: %s (%d) must be exactly %d" % (
                    cls.name,
                    param,
                    salt_size,
                    mn,
                )
                if relaxed:
                    warn(msg, PasslibHashWarning)
                else:
                    raise ValueError(msg)
            return mn

        # check min size
        if salt_size < mn:
            msg = "%s: %s (%r) below min_salt_size (%d)" % (
                cls.name,
                param,
                salt_size,
                mn,
            )
            if relaxed:
                warn(msg, PasslibHashWarning)
                salt_size = mn
            else:
                raise ValueError(msg)

        # check max size
        if mx and salt_size > mx:
            msg = "%s: %s (%r) above max_salt_size (%d)" % (
                cls.name,
                param,
                salt_size,
                mx,
            )
            if relaxed:
                warn(msg, PasslibHashWarning)
                salt_size = mx
            else:
                raise ValueError(msg)

        return salt_size

    def __init__(self, salt=None, **kwds):
        super().__init__(**kwds)
        if salt is not None:
            salt = self._parse_salt(salt)
        elif self.use_defaults:
            salt = self._generate_salt()
            assert self._norm_salt(salt) == salt, "generated invalid salt: %r" % (salt,)
        else:
            raise TypeError("no salt specified")
        self.salt = salt

    # NOTE: split out mainly so sha256_crypt can subclass this
    def _parse_salt(self, salt):
        return self._norm_salt(salt)

    @classmethod
    def _norm_salt(cls, salt, relaxed=False):
        """helper to normalize & validate user-provided salt string

        :arg salt:
            salt string

        :raises TypeError:
            If salt not correct type.

        :raises ValueError:

            * if salt contains chars that aren't in :attr:`salt_chars`.
            * if salt contains less than :attr:`min_salt_size` characters.
            * if ``relaxed=False`` and salt has more than :attr:`max_salt_size`
              characters (if ``relaxed=True``, the salt is truncated
              and a warning is issued instead).

        :returns:
            normalized salt
        """
        # check type
        if cls._salt_is_bytes:
            if not isinstance(salt, bytes):
                raise exc.ExpectedTypeError(salt, "bytes", "salt")
        else:
            if not isinstance(salt, str):
                # NOTE: allowing bytes under py2 so salt can be native str.
                if relaxed and isinstance(salt, bytes):
                    salt = salt.decode("ascii")
                else:
                    raise exc.ExpectedTypeError(salt, "str", "salt")

            # check charset
            sc = cls.salt_chars
            if sc is not None and any(c not in sc for c in salt):
                raise ValueError("invalid characters in %s salt" % cls.name)

        # check min size
        mn = cls.min_salt_size
        if mn and len(salt) < mn:
            msg = "salt too small (%s requires %s %d %s)" % (
                cls.name,
                "exactly" if mn == cls.max_salt_size else ">=",
                mn,
                cls._salt_unit,
            )
            raise ValueError(msg)

        # check max size
        mx = cls.max_salt_size
        if mx and len(salt) > mx:
            msg = "salt too large (%s requires %s %d %s)" % (
                cls.name,
                "exactly" if mx == mn else "<=",
                mx,
                cls._salt_unit,
            )
            if relaxed:
                warn(msg, PasslibHashWarning)
                salt = cls._truncate_salt(salt, mx)
            else:
                raise ValueError(msg)

        return salt

    @staticmethod
    def _truncate_salt(salt, mx):
        # NOTE: some hashes (e.g. bcrypt) has structure within their
        # salt string. this provides a method to override to perform
        # the truncation properly
        return salt[:mx]

    @classmethod
    def _generate_salt(cls):
        """
        helper method for _init_salt(); generates a new random salt string.
        """
        return getrandstr(rng, cls.default_salt_chars, cls.default_salt_size)

    @classmethod
    def bitsize(cls, salt_size=None, **kwds):
        """[experimental method] return info about bitsizes of hash"""
        info = super().bitsize(**kwds)
        if salt_size is None:
            salt_size = cls.default_salt_size
        # FIXME: this may overestimate size due to padding bits
        # FIXME: this will be off by 1 for case-insensitive hashes.
        info["salt"] = _bitsize(salt_size, cls.default_salt_chars)
        return info


class HasRawSalt(HasSalt):
    """mixin for classes which use decoded salt parameter

    A variant of :class:`!HasSalt` which takes in decoded bytes instead of an encoded string.

    .. todo::

        document this class's usage
    """

    salt_chars = ALL_BYTE_VALUES

    # NOTE: all HasRawSalt code is currently part of HasSalt, using private
    # '_salt_is_bytes' flag. this arrangement may be changed in the future.
    _salt_is_bytes = True
    _salt_unit = "bytes"

    @classmethod
    def _generate_salt(cls):
        assert cls.salt_chars in [None, ALL_BYTE_VALUES]
        return getrandbytes(rng, cls.default_salt_size)


class HasRounds(GenericHandler):
    """mixin for validating rounds parameter

    This :class:`GenericHandler` mixin adds a ``rounds`` keyword to the class
    constuctor; any value provided is passed through the :meth:`_norm_rounds`
    method, which takes care of validating the number of rounds.

    :param rounds: optional number of rounds hash should use

    Class Attributes
    ================
    In order for :meth:`!_norm_rounds` to do its job, the following
    attributes must be provided by the handler subclass:

    .. attribute:: min_rounds

        The minimum number of rounds allowed. A :exc:`ValueError` will be
        thrown if the rounds value is too small. Defaults to ``0``.

    .. attribute:: max_rounds

        The maximum number of rounds allowed. A :exc:`ValueError` will be
        thrown if the rounds value is larger than this. Defaults to ``None``
        which indicates no limit to the rounds value.

    .. attribute:: default_rounds

        If no rounds value is provided to constructor, this value will be used.
        If this is not specified, a rounds value *must* be specified by the
        application.

    .. attribute:: rounds_cost

        [required]
        The ``rounds`` parameter typically encodes a cpu-time cost
        for calculating a hash. This should be set to ``"linear"``
        (the default) or ``"log2"``, depending on how the rounds value relates
        to the actual amount of time that will be required.

    Class Methods
    =============
    .. todo:: document using() and needs_update() options

    Instance Attributes
    ===================
    .. attribute:: rounds

        This instance attribute will be filled in with the rounds value provided
        to the constructor (as adapted by :meth:`_norm_rounds`)

    Subclassable Methods
    ====================
    .. automethod:: _norm_rounds
    """

    # -----------------
    # algorithm options -- not application configurable
    # -----------------
    # XXX: rename to min_valid_rounds / max_valid_rounds,
    #      to clarify role compared to min_desired_rounds / max_desired_rounds?
    min_rounds: int = 0
    max_rounds: Optional[int] = None
    rounds_cost: str = "linear"  # default to the common case

    # hack to pass info to _CryptRecord (will be removed in passlib 2.0)
    using_rounds_kwds = (
        "min_desired_rounds",
        "max_desired_rounds",
        "min_rounds",
        "max_rounds",
        "default_rounds",
        "vary_rounds",
    )

    # -----------------
    # desired & default rounds -- configurable via .using() classmethod
    # -----------------
    min_desired_rounds = None
    max_desired_rounds = None
    default_rounds: Optional[int] = None
    vary_rounds = None
    rounds = None

    @classmethod
    def using(
        cls,
        min_desired_rounds=None,
        max_desired_rounds=None,
        default_rounds=None,
        vary_rounds: Union[str, float, None] = None,
        min_rounds=None,
        max_rounds=None,
        rounds=None,  # aliases used by CryptContext
        **kwds,
    ):
        # check for aliases used by CryptContext
        if min_rounds is not None:
            if min_desired_rounds is not None:
                raise TypeError(
                    "'min_rounds' and 'min_desired_rounds' aliases are mutually exclusive"
                )
            min_desired_rounds = min_rounds

        if max_rounds is not None:
            if max_desired_rounds is not None:
                raise TypeError(
                    "'max_rounds' and 'max_desired_rounds' aliases are mutually exclusive"
                )
            max_desired_rounds = max_rounds

        # use 'rounds' as fallback for min, max, AND default
        # XXX: would it be better to make 'default_rounds' and 'rounds'
        #      aliases, and have a separate 'require_rounds' parameter for this behavior?
        if rounds is not None:
            if min_desired_rounds is None:
                min_desired_rounds = rounds
            if max_desired_rounds is None:
                max_desired_rounds = rounds
            if default_rounds is None:
                default_rounds = rounds

        # generate new subclass
        subcls = super().using(**kwds)

        # replace min_desired_rounds
        relaxed = kwds.get("relaxed")
        if min_desired_rounds is None:
            explicit_min_rounds = False
            min_desired_rounds = cls.min_desired_rounds
        else:
            explicit_min_rounds = True
            if isinstance(min_desired_rounds, str):
                min_desired_rounds = int(min_desired_rounds)
            subcls.min_desired_rounds = subcls._norm_rounds(
                min_desired_rounds, param="min_desired_rounds", relaxed=relaxed
            )

        # replace max_desired_rounds
        if max_desired_rounds is None:
            max_desired_rounds = cls.max_desired_rounds
        else:
            if isinstance(max_desired_rounds, str):
                max_desired_rounds = int(max_desired_rounds)
            if min_desired_rounds and max_desired_rounds < min_desired_rounds:
                msg = "%s: max_desired_rounds (%r) below min_desired_rounds (%r)" % (
                    subcls.name,
                    max_desired_rounds,
                    min_desired_rounds,
                )
                if explicit_min_rounds:
                    raise ValueError(msg)
                else:
                    warn(msg, PasslibConfigWarning)
                    max_desired_rounds = min_desired_rounds
            subcls.max_desired_rounds = subcls._norm_rounds(
                max_desired_rounds, param="max_desired_rounds", relaxed=relaxed
            )

        # replace default_rounds
        if default_rounds is not None:
            if isinstance(default_rounds, str):
                default_rounds = int(default_rounds)
            if min_desired_rounds and default_rounds < min_desired_rounds:
                raise ValueError(
                    "%s: default_rounds (%r) below min_desired_rounds (%r)"
                    % (subcls.name, default_rounds, min_desired_rounds)
                )
            elif max_desired_rounds and default_rounds > max_desired_rounds:
                raise ValueError(
                    "%s: default_rounds (%r) above max_desired_rounds (%r)"
                    % (subcls.name, default_rounds, max_desired_rounds)
                )
            subcls.default_rounds = subcls._norm_rounds(
                default_rounds, param="default_rounds", relaxed=relaxed
            )

        # clip default rounds to new limits.
        if subcls.default_rounds is not None:
            subcls.default_rounds = subcls._clip_to_desired_rounds(
                subcls.default_rounds
            )

        # replace / set vary_rounds
        if vary_rounds is not None:
            if isinstance(vary_rounds, str):
                if vary_rounds.endswith("%"):
                    vary_rounds = float(vary_rounds[:-1]) * 0.01
                elif "." in vary_rounds:
                    vary_rounds = float(vary_rounds)
                else:
                    vary_rounds = int(vary_rounds)
            if vary_rounds < 0:
                raise ValueError(
                    "%s: vary_rounds (%r) below 0" % (subcls.name, vary_rounds)
                )
            elif isinstance(vary_rounds, float):
                # TODO: deprecate / disallow vary_rounds=1.0
                if vary_rounds > 1:
                    raise ValueError(
                        "%s: vary_rounds (%r) above 1.0" % (subcls.name, vary_rounds)
                    )
            elif not isinstance(vary_rounds, int):
                raise TypeError("vary_rounds must be int or float")
            if vary_rounds:
                warn(
                    "The 'vary_rounds' option is deprecated as of Passlib 1.7, "
                    "and will be removed in Passlib 2.0",
                    PasslibConfigWarning,
                )
            subcls.vary_rounds = vary_rounds
            # XXX: could cache _calc_vary_rounds_range() here if needed,
            #      but would need to handle user manually changing .default_rounds
        return subcls

    @classmethod
    def _clip_to_desired_rounds(cls, rounds):
        """
        helper for :meth:`_generate_rounds` --
        clips rounds value to desired min/max set by class (if any)
        """
        # NOTE: min/max_desired_rounds are None if unset.
        # check minimum
        mnd = cls.min_desired_rounds or 0
        if rounds < mnd:
            return mnd

        # check maximum
        mxd = cls.max_desired_rounds
        if mxd and rounds > mxd:
            return mxd

        return rounds

    @classmethod
    def _calc_vary_rounds_range(cls, default_rounds):
        """
        helper for :meth:`_generate_rounds` --
        returns range for vary rounds generation.

        :returns:
            (lower, upper) limits suitable for random.randint()
        """
        # XXX: could precalculate output of this in using() method, and save per-hash cost.
        #      but then users patching cls.vary_rounds / cls.default_rounds would get wrong value.
        assert default_rounds
        vary_rounds = cls.vary_rounds

        # if vary_rounds specified as % of default, convert it to actual rounds
        def linear_to_native(value, upper):
            return value

        if isinstance(vary_rounds, float):
            assert 0 <= vary_rounds <= 1  # TODO: deprecate vary_rounds==1
            if cls.rounds_cost == "log2":
                # special case -- have to convert default_rounds to linear scale,
                # apply +/- vary_rounds to that, and convert back to log scale again.
                # linear_to_native() takes care of the "convert back" step.
                default_rounds = 1 << default_rounds

                def linear_to_native(value, upper):
                    if value <= 0:  # log() undefined for <= 0
                        return 0
                    elif upper:  # use smallest upper bound for start of range
                        return int(math.log(value, 2))
                    else:  # use greatest lower bound for end of range
                        return int(math.ceil(math.log(value, 2)))

            # calculate integer vary rounds based on current default_rounds
            vary_rounds = int(default_rounds * vary_rounds)

        # calculate bounds based on default_rounds +/- vary_rounds
        assert vary_rounds >= 0 and isinstance(vary_rounds, int)
        lower = linear_to_native(default_rounds - vary_rounds, False)
        upper = linear_to_native(default_rounds + vary_rounds, True)
        return cls._clip_to_desired_rounds(lower), cls._clip_to_desired_rounds(upper)

    def __init__(self, rounds=None, **kwds):
        super().__init__(**kwds)
        if rounds is not None:
            rounds = self._parse_rounds(rounds)
        elif self.use_defaults:
            rounds = self._generate_rounds()
            assert self._norm_rounds(rounds) == rounds, (
                "generated invalid rounds: %r" % (rounds,)
            )
        else:
            raise TypeError("no rounds specified")
        self.rounds = rounds

    # NOTE: split out mainly so sha256_crypt & bsdi_crypt can subclass this
    def _parse_rounds(self, rounds):
        return self._norm_rounds(rounds)

    @classmethod
    def _norm_rounds(cls, rounds, relaxed=False, param="rounds"):
        """
        helper for normalizing rounds value.

        :arg rounds:
            an integer cost parameter.

        :param relaxed:
            if ``True`` (the default), issues PasslibHashWarning is rounds are outside allowed range.
            if ``False``, raises a ValueError instead.

        :param param:
            optional name of parameter to insert into error/warning messages.

        :raises TypeError:
            * if ``use_defaults=False`` and no rounds is specified
            * if rounds is not an integer.

        :raises ValueError:

            * if rounds is ``None`` and class does not specify a value for
              :attr:`default_rounds`.
            * if ``relaxed=False`` and rounds is outside bounds of
              :attr:`min_rounds` and :attr:`max_rounds` (if ``relaxed=True``,
              the rounds value will be clamped, and a warning issued).

        :returns:
            normalized rounds value
        """
        return norm_integer(
            cls, rounds, cls.min_rounds, cls.max_rounds, param=param, relaxed=relaxed
        )

    @classmethod
    def _generate_rounds(cls):
        """
        internal helper for :meth:`_norm_rounds` --
        returns default rounds value, incorporating vary_rounds,
        and any other limitations hash may place on rounds parameter.
        """
        # load default rounds
        rounds = cls.default_rounds
        if rounds is None:
            raise TypeError(
                "%s rounds value must be specified explicitly" % (cls.name,)
            )

        # randomly vary the rounds slightly basic on vary_rounds parameter.
        # reads default_rounds internally.
        if cls.vary_rounds:
            lower, upper = cls._calc_vary_rounds_range(rounds)
            assert lower <= rounds <= upper
            if lower < upper:
                rounds = rng.randint(lower, upper)

        return rounds

    def _calc_needs_update(self, **kwds):
        """
        mark hash as needing update if rounds is outside desired bounds.
        """
        min_desired_rounds = self.min_desired_rounds
        if min_desired_rounds and self.rounds < min_desired_rounds:
            return True
        max_desired_rounds = self.max_desired_rounds
        if max_desired_rounds and self.rounds > max_desired_rounds:
            return True
        return super()._calc_needs_update(**kwds)

    @classmethod
    def bitsize(cls, rounds=None, vary_rounds=0.1, **kwds):
        """[experimental method] return info about bitsizes of hash"""
        info = super().bitsize(**kwds)
        # NOTE: this essentially estimates how many bits of "salt"
        # can be added by varying the rounds value just a little bit.
        if cls.rounds_cost != "log2":
            # assume rounds can be randomized within the range
            #     rounds*(1-vary_rounds) ... rounds*(1+vary_rounds)
            # then this can be used to encode
            #     log2(rounds*(1+vary_rounds)-rounds*(1-vary_rounds))
            # worth of salt-like bits. this works out to
            #     1+log2(rounds*vary_rounds)
            import math

            if rounds is None:
                rounds = cls.default_rounds
            info["rounds"] = max(0, int(1 + math.log(rounds * vary_rounds, 2)))
        ## else: # log2 rounds
        # all bits of the rounds value are critical to choosing
        # the time-cost, and can't be randomized.
        return info


class ParallelismMixin(GenericHandler):
    """
    mixin which provides common behavior for 'parallelism' setting
    """

    # NOTE: subclasses should add "parallelism" to their settings_kwds

    #: parallelism setting (class-level value used as default)
    parallelism = 1

    @classmethod
    def using(cls, parallelism=None, **kwds):
        subcls = super().using(**kwds)
        if parallelism is not None:
            if isinstance(parallelism, str):
                parallelism = int(parallelism)
            subcls.parallelism = subcls._norm_parallelism(
                parallelism, relaxed=kwds.get("relaxed")
            )
        return subcls

    def __init__(self, parallelism=None, **kwds):
        super().__init__(**kwds)

        # init parallelism
        if parallelism is None:
            assert validate_default_value(
                self, self.parallelism, self._norm_parallelism, param="parallelism"
            )
        else:
            self.parallelism = self._norm_parallelism(parallelism)

    @classmethod
    def _norm_parallelism(cls, parallelism, relaxed=False):
        return norm_integer(
            cls, parallelism, min=1, param="parallelism", relaxed=relaxed
        )

    def _calc_needs_update(self, **kwds):
        """
        mark hash as needing update if rounds is outside desired bounds.
        """
        # XXX: for now, marking all hashes which don't have matching parallelism setting
        if self.parallelism != type(self).parallelism:
            return True
        return super()._calc_needs_update(**kwds)


#: global lock that must be held when changing backends.
#: not bothering to make this more granular, as backend switching
#: isn't a speed-critical path.  lock is needed since there is some
#: class-level state that may be modified during a "dry run"
_backend_lock = threading.RLock()


class BackendMixin(PasswordHash):
    """
    PasswordHash mixin which provides generic framework for supporting multiple backends
    within the class.

    Public API
    ----------

    .. attribute:: backends

        This attribute should be a tuple containing the names of the backends
        which are supported. Two common names are ``"os_crypt"`` (if backend
        uses :mod:`crypt`), and ``"builtin"`` (if the backend is a pure-python
        fallback).

    .. automethod:: get_backend
    .. automethod:: set_backend
    .. automethod:: has_backend

    .. warning::

        :meth:`set_backend` is intended to be called during application startup --
        it affects global state, and switching backends is not guaranteed threadsafe.

    Private API (Subclass Hooks)
    ----------------------------
    Subclasses should set the :attr:`!backends` attribute to a tuple of the backends
    they wish to support.  They should also define one method:

    .. classmethod:: _load_backend_{name}(dryrun=False)

        One copy of this method should be defined for each :samp:`name` within :attr:`!backends`.

        It will be called in order to load the backend, and should take care of whatever
        is needed to enable the backend.  This may include importing modules, running tests,
        issuing warnings, etc.

        :param name:
            [Optional] name of backend.

        :param dryrun:
            [Optional] True/False if currently performing a "dry run".

            if True, the method should perform all setup actions *except*
            switching the class over to the new backend.

        :raises passlib.exc.PasslibSecurityError:
            if the backend is available, but cannot be loaded due to a security issue.

        :returns:
            False if backend not available, True if backend loaded.

        .. warning::

            Due to the way passlib's internals are arranged,
            backends should generally store stateful data at the class level
            (not the module level), and be prepared to be called on subclasses
            which may be set to a different backend from their parent.

            (Idempotent module-level data such as lazy imports are fine).

    .. automethod:: _finalize_backend

    .. versionadded:: 1.7
    """

    #: list of backend names, provided by subclass.
    backends = None

    #: private attr mixin uses to hold currently loaded backend (or ``None``)
    __backend = None

    #: optional class-specific text containing suggestion about what to do
    #: when no backends are available.
    _no_backend_suggestion = None

    #: shared attr used by set_backend() to indicate what backend it's loaded;
    #: meaningless while not in set_backend().
    _pending_backend = None

    #: shared attr used by set_backend() to indicate if it's in "dry run" mode;
    #: meaningless while not in set_backend().
    _pending_dry_run = False

    @classmethod
    def get_backend(cls):
        """
        Return name of currently active backend.
        if no backend has been loaded, loads and returns name of default backend.

        :raises passlib.exc.MissingBackendError:
            if no backends are available.

        :returns:
            name of active backend
        """
        if not cls.__backend:
            cls.set_backend()
            assert cls.__backend, "set_backend() failed to load a default backend"
        return cls.__backend

    @classmethod
    def has_backend(cls, name="any"):
        """
        Check if support is currently available for specified backend.

        :arg name:
            name of backend to check for.
            can be any string accepted by :meth:`set_backend`.

        :raises ValueError:
            if backend name is unknown

        :returns:
            * ``True`` if backend is available.
            * ``False`` if it's available / can't be loaded.
            * ``None`` if it's present, but won't load due to a security issue.
        """
        try:
            cls.set_backend(name, dryrun=True)
            return True
        except (exc.MissingBackendError, exc.PasslibSecurityError):
            return False

    @classmethod
    def set_backend(cls, name="any", dryrun=False):
        """
        Load specified backend.

        :arg name:
            name of backend to load, can be any of the following:

            * ``"any"`` -- use current backend if one is loaded,
              otherwise load the first available backend.

            * ``"default"`` -- use the first available backend.

            * any string in :attr:`backends`, loads specified backend.

        :param dryrun:
            If True, this perform all setup actions *except* switching over to the new backend.
            (this flag is used to implement :meth:`has_backend`).

            .. versionadded:: 1.7

        :raises ValueError:
            If backend name is unknown.

        :raises passlib.exc.MissingBackendError:
            If specific backend is missing;
            or in the case of ``"any"`` / ``"default"``, if *no* backends are available.

        :raises passlib.exc.PasslibSecurityError:

            If ``"any"`` or ``"default"`` was specified,
            but the only backend available has a PasslibSecurityError.
        """
        # check if active backend is acceptable
        if (name == "any" and cls.__backend) or (name and name == cls.__backend):
            return cls.__backend

        # if this isn't the final subclass, whose bases we can modify,
        # find that class, and recursively call this method for the proper class.
        owner = cls._get_backend_owner()
        if owner is not cls:
            return owner.set_backend(name, dryrun=dryrun)

        # pick first available backend
        if name == "any" or name == "default":
            default_error = None
            for name in cls.backends:
                try:
                    return cls.set_backend(name, dryrun=dryrun)
                except exc.MissingBackendError:
                    continue
                except exc.PasslibSecurityError as err:
                    # backend is available, but refuses to load due to security issue.
                    if default_error is None:
                        default_error = err
                    continue
            if default_error is None:
                msg = "%s: no backends available" % cls.name
                if cls._no_backend_suggestion:
                    msg += cls._no_backend_suggestion
                default_error = exc.MissingBackendError(msg)
            raise default_error

        # validate name
        if name not in cls.backends:
            raise exc.UnknownBackendError(cls, name)

        # hand off to _set_backend()
        with _backend_lock:
            orig = cls._pending_backend, cls._pending_dry_run
            try:
                cls._pending_backend = name
                cls._pending_dry_run = dryrun
                cls._set_backend(name, dryrun)
            finally:
                cls._pending_backend, cls._pending_dry_run = orig
            if not dryrun:
                cls.__backend = name
            return name

    @classmethod
    def _get_backend_owner(cls):
        """
        return class that set_backend() should actually be modifying.
        for SubclassBackendMixin, this may not always be the class that was invoked.
        """
        return cls

    @classmethod
    def _set_backend(cls, name, dryrun):
        """
        Internal method invoked by :meth:`set_backend`.
        handles actual loading of specified backend.

        global _backend_lock will be held for duration of this method,
        and _pending_dry_run & _pending_backend will also be set.

        should return True / False.
        """
        loader = cls._get_backend_loader(name)
        kwds = {}
        if accepts_keyword(loader, "name"):
            kwds["name"] = name
        if accepts_keyword(loader, "dryrun"):
            kwds["dryrun"] = dryrun
        ok = loader(**kwds)
        if ok is False:
            raise exc.MissingBackendError(
                "%s: backend not available: %s" % (cls.name, name)
            )
        elif ok is not True:
            raise AssertionError(
                "backend loaders must return True or False" ": %r" % (ok,)
            )

    @classmethod
    def _get_backend_loader(cls, name):
        """
        Hook called to get the specified backend's loader.
        Should return callable which optionally takes ``"name"`` and/or
        ``"dryrun"`` keywords.

        Callable should return True if backend initialized successfully.

        If backend can't be loaded, callable should return False
        OR raise MissingBackendError directly.
        """
        raise NotImplementedError("implement in subclass")

    @classmethod
    def _stub_requires_backend(cls):
        """
        helper for subclasses to create stub methods which auto-load backend.
        """
        if cls.__backend:
            raise AssertionError(
                "%s: _finalize_backend(%r) failed to replace lazy loader"
                % (cls.name, cls.__backend)
            )
        cls.set_backend()
        if not cls.__backend:
            raise AssertionError(
                "%s: set_backend() failed to load a default backend" % (cls.name)
            )


class SubclassBackendMixin(BackendMixin):
    """
    variant of BackendMixin which allows backends to be implemented
    as separate mixin classes, and dynamically switches them out.

    backend classes should implement a _load_backend() classmethod,
    which will be invoked with an optional 'dryrun' keyword,
    and should return True or False.

    _load_backend() will be invoked with ``cls`` equal to the mixin,
    *not* the overall class.

    .. versionadded:: 1.7
    """

    # 'backends' required by BackendMixin

    #: NON-INHERITED flag that this class's bases should be modified by SubclassBackendMixin.
    #: should only be set to True in *one* subclass in hierarchy.
    _backend_mixin_target = False

    #: map of backend name -> mixin class
    _backend_mixin_map = None

    @classmethod
    def _get_backend_owner(cls):
        """
        return base class that we're actually switching backends on
        (needed in since backends frequently modify class attrs,
        and .set_backend may be called from a subclass).
        """
        if not cls._backend_mixin_target:
            raise AssertionError("_backend_mixin_target not set")
        for base in cls.__mro__:
            if base.__dict__.get("_backend_mixin_target"):
                return base
        raise AssertionError("expected to find class w/ '_backend_mixin_target' set")

    @classmethod
    def _set_backend(cls, name, dryrun):
        # invoke backend loader (will throw error if fails)
        super()._set_backend(name, dryrun)

        # sanity check call args (should trust .set_backend, but will really
        # foul things up if this isn't the owner)
        assert (
            cls is cls._get_backend_owner()
        ), "_finalize_backend() not invoked on owner"

        # pick mixin class
        mixin_map = cls._backend_mixin_map
        assert mixin_map, "_backend_mixin_map not specified"
        mixin_cls = mixin_map[name]
        assert issubclass(mixin_cls, SubclassBackendMixin), "invalid mixin class"

        # modify <cls> to remove existing backend mixins, and insert the new one
        update_mixin_classes(
            cls,
            add=mixin_cls,
            remove=mixin_map.values(),
            append=True,
            before=SubclassBackendMixin,
            dryrun=dryrun,
        )

    @classmethod
    def _get_backend_loader(cls, name):
        assert cls._backend_mixin_map, "_backend_mixin_map not specified"
        return cls._backend_mixin_map[name]._load_backend_mixin


# XXX: rename to ChecksumBackendMixin?
class HasManyBackends(BackendMixin, GenericHandler):
    """
    GenericHandler mixin which provides selecting from multiple backends.

    .. todo::

        finish documenting this class's usage

    For hashes which need to select from multiple backends,
    depending on the host environment, this class
    offers a way to specify alternate :meth:`_calc_checksum` methods,
    and will dynamically chose the best one at runtime.

    .. versionchanged:: 1.7

        This class now derives from :class:`BackendMixin`, which abstracts
        out a more generic framework for supporting multiple backends.
        The public api (:meth:`!get_backend`, :meth:`!has_backend`, :meth:`!set_backend`)
        is roughly the same.

    Private API (Subclass Hooks)
    ----------------------------
    As of version 1.7, classes should implement :meth:`!_load_backend_{name}`, per
    :class:`BackendMixin`.  This hook should invoke :meth:`!_set_calc_checksum_backcend`
    to install it's backend method.

    .. deprecated:: 1.7

        The following api is deprecated, and will be removed in Passlib 2.0:

    .. attribute:: _has_backend_{name}

        private class attribute checked by :meth:`has_backend` to see if a
        specific backend is available, it should be either ``True``
        or ``False``. One of these should be provided by
        the subclass for each backend listed in :attr:`backends`.

    .. classmethod:: _calc_checksum_{name}

        private class method that should implement :meth:`_calc_checksum`
        for a given backend. it will only be called if the backend has
        been selected by :meth:`set_backend`. One of these should be provided
        by the subclass for each backend listed in :attr:`backends`.
    """

    def _calc_checksum(self, secret):
        "wrapper for backend, for common code" ""
        # NOTE: not overwriting _calc_checksum() directly, so that classes can provide
        #       common behavior in that method,
        #       and then invoke _calc_checksum_backend() to do the work.
        return self._calc_checksum_backend(secret)

    def _calc_checksum_backend(self, secret):
        """
        stub for _calc_checksum_backend() --
        should load backend if one hasn't been loaded;
        if one has been loaded, this method should have been monkeypatched by _finalize_backend().
        """
        self._stub_requires_backend()
        return self._calc_checksum_backend(secret)

    @classmethod
    def _get_backend_loader(cls, name):
        """
        subclassed to support legacy 1.6 HasManyBackends api.
        (will be removed in passlib 2.0)
        """
        # check for 1.7 loader
        loader = getattr(cls, "_load_backend_" + name, None)
        if loader is None:
            # fallback to pre-1.7 _has_backend_xxx + _calc_checksum_xxx() api
            def loader():
                return cls.__load_legacy_backend(name)
        else:
            # make sure 1.6 api isn't defined at same time
            assert not hasattr(cls, "_has_backend_" + name), (
                "%s: can't specify both ._load_backend_%s() "
                "and ._has_backend_%s" % (cls.name, name, name)
            )
        return loader

    @classmethod
    def __load_legacy_backend(cls, name):
        value = getattr(cls, "_has_backend_" + name)
        warn(
            "%s: support for ._has_backend_%s is deprecated as of Passlib 1.7, "
            "and will be removed in Passlib 1.9/2.0, please implement "
            "._load_backend_%s() instead" % (cls.name, name, name),
            DeprecationWarning,
        )
        if value:
            func = getattr(cls, "_calc_checksum_" + name)
            cls._set_calc_checksum_backend(func)
            return True
        else:
            return False

    @classmethod
    def _set_calc_checksum_backend(cls, func):
        """
        helper used by subclasses to validate & set backend-specific
        calc checksum helper.
        """
        backend = cls._pending_backend
        assert backend, "should only be called during set_backend()"
        if not callable(func):
            raise RuntimeError(
                "%s: backend %r returned invalid callable: %r"
                % (cls.name, backend, func)
            )
        if not cls._pending_dry_run:
            cls._calc_checksum_backend = func


# XXX: should this inherit from PasswordHash?
class PrefixWrapper(object):
    """wraps another handler, adding a constant prefix.

    instances of this class wrap another password hash handler,
    altering the constant prefix that's prepended to the wrapped
    handlers' hashes.

    this is used mainly by the :doc:`ldap crypt <passlib.hash.ldap_crypt>` handlers;
    such as :class:`~passlib.hash.ldap_md5_crypt` which wraps :class:`~passlib.hash.md5_crypt` and adds a ``{CRYPT}`` prefix.

    usage::

        myhandler = PrefixWrapper("myhandler", "md5_crypt", prefix="$mh$", orig_prefix="$1$")

    :param name: name to assign to handler
    :param wrapped: handler object or name of registered handler
    :param prefix: identifying prefix to prepend to all hashes
    :param orig_prefix: prefix to strip (defaults to '').
    :param lazy: if True and wrapped handler is specified by name, don't look it up until needed.
    """

    #: list of attributes which should be cloned by .using()
    _using_clone_attrs = ()

    def __init__(
        self, name, wrapped, prefix="", orig_prefix="", lazy=False, doc=None, ident=None
    ):
        self.name = name
        if isinstance(prefix, bytes):
            prefix = prefix.decode("ascii")
        self.prefix = prefix
        if isinstance(orig_prefix, bytes):
            orig_prefix = orig_prefix.decode("ascii")
        self.orig_prefix = orig_prefix
        if doc:
            self.__doc__ = doc
        if hasattr(wrapped, "name"):
            self._set_wrapped(wrapped)
        else:
            self._wrapped_name = wrapped
            if not lazy:
                self._get_wrapped()

        if ident is not None:
            if ident is True:
                # signal that prefix is identifiable in itself.
                if prefix:
                    ident = prefix
                else:
                    raise ValueError("no prefix specified")
            if isinstance(ident, bytes):
                ident = ident.decode("ascii")
            # XXX: what if ident includes parts of wrapped hash's ident?
            if ident[: len(prefix)] != prefix[: len(ident)]:
                raise ValueError("ident must agree with prefix")
            self._ident = ident

    _wrapped_name = None
    _wrapped_handler = None

    def _set_wrapped(self, handler):
        # check this is a valid handler
        if "ident" in handler.setting_kwds and self.orig_prefix:
            # TODO: look into way to fix the issues.
            warn(
                "PrefixWrapper: 'orig_prefix' option may not work correctly "
                "for handlers which have multiple identifiers: %r" % (handler.name,),
                exc.PasslibRuntimeWarning,
            )

        # store reference
        self._wrapped_handler = handler

    def _get_wrapped(self):
        handler = self._wrapped_handler
        if handler is None:
            handler = get_crypt_handler(self._wrapped_name)
            self._set_wrapped(handler)
        return handler

    wrapped = property(_get_wrapped)

    _ident = False

    @property
    def ident(self):
        value = self._ident
        if value is False:
            value = None
            # XXX: how will this interact with orig_prefix ?
            #      not exposing attrs for now if orig_prefix is set.
            if not self.orig_prefix:
                wrapped = self.wrapped
                ident = getattr(wrapped, "ident", None)
                if ident is not None:
                    value = self._wrap_hash(ident)
            self._ident = value
        return value

    _ident_values = False

    @property
    def ident_values(self):
        value = self._ident_values
        if value is False:
            value = None
            # XXX: how will this interact with orig_prefix ?
            #      not exposing attrs for now if orig_prefix is set.
            if not self.orig_prefix:
                wrapped = self.wrapped
                idents = getattr(wrapped, "ident_values", None)
                if idents:
                    value = tuple(self._wrap_hash(ident) for ident in idents)
                ##else:
                ##    ident = self.ident
                ##    if ident is not None:
                ##        value = [ident]
            self._ident_values = value
        return value

    # attrs that should be proxied
    # XXX: change this to proxy everything that doesn't start with "_"?
    _proxy_attrs = (
        "setting_kwds",
        "context_kwds",
        "default_rounds",
        "min_rounds",
        "max_rounds",
        "rounds_cost",
        "min_desired_rounds",
        "max_desired_rounds",
        "vary_rounds",
        "default_salt_size",
        "min_salt_size",
        "max_salt_size",
        "salt_chars",
        "default_salt_chars",
        "backends",
        "has_backend",
        "get_backend",
        "set_backend",
        "is_disabled",
        "truncate_size",
        "truncate_error",
        "truncate_verify_reject",
        # internal info attrs needed for test inspection
        "_salt_is_bytes",
    )

    def __repr__(self):
        args = [repr(self._wrapped_name or self._wrapped_handler)]
        if self.prefix:
            args.append("prefix=%r" % self.prefix)
        if self.orig_prefix:
            args.append("orig_prefix=%r" % self.orig_prefix)
        args = ", ".join(args)
        return "PrefixWrapper(%r, %s)" % (self.name, args)

    def __dir__(self):
        attrs = set(dir(self.__class__))
        attrs.update(self.__dict__)
        wrapped = self.wrapped
        attrs.update(attr for attr in self._proxy_attrs if hasattr(wrapped, attr))
        return list(attrs)

    def __getattr__(self, attr):
        """proxy most attributes from wrapped class (e.g. rounds, salt size, etc)"""
        if attr in self._proxy_attrs:
            return getattr(self.wrapped, attr)
        raise AttributeError("missing attribute: %r" % (attr,))

    def __setattr__(self, attr, value):
        # if proxy attr present on wrapped object,
        # and we own it, modify *it* instead.
        # TODO: needs UTs
        # TODO: any other cases where wrapped is "owned"?
        #       currently just if created via .using()
        if attr in self._proxy_attrs and self._derived_from:
            wrapped = self.wrapped
            if hasattr(wrapped, attr):
                setattr(wrapped, attr, value)
                return
        return object.__setattr__(self, attr, value)

    def _unwrap_hash(self, hash):
        """given hash belonging to wrapper, return orig version"""
        # NOTE: assumes hash has been validated as unicode already
        prefix = self.prefix
        if not hash.startswith(prefix):
            raise exc.InvalidHashError(self)
        # NOTE: always passing to handler as unicode, to save reconversion
        return self.orig_prefix + hash[len(prefix) :]

    def _wrap_hash(self, hash):
        """given orig hash; return one belonging to wrapper"""
        # NOTE: should usually be native string.
        # (which does mean extra work under py2, but not py3)
        if isinstance(hash, bytes):
            hash = hash.decode("ascii")
        orig_prefix = self.orig_prefix
        if not hash.startswith(orig_prefix):
            raise exc.InvalidHashError(self.wrapped)
        wrapped = self.prefix + hash[len(orig_prefix) :]
        return wrapped

    #: set by _using(), helper for test harness' handler_derived_from()
    _derived_from = None

    def using(self, **kwds):
        # generate subclass of wrapped handler
        subcls = self.wrapped.using(**kwds)
        assert subcls is not self.wrapped
        # then create identical wrapper which wraps the new subclass.
        wrapper = PrefixWrapper(
            self.name, subcls, prefix=self.prefix, orig_prefix=self.orig_prefix
        )
        wrapper._derived_from = self
        for attr in self._using_clone_attrs:
            setattr(wrapper, attr, getattr(self, attr))
        return wrapper

    def needs_update(self, hash, **kwds):
        hash = self._unwrap_hash(hash)
        return self.wrapped.needs_update(hash, **kwds)

    def identify(self, hash):
        hash = to_unicode_for_identify(hash)
        if not hash.startswith(self.prefix):
            return False
        hash = self._unwrap_hash(hash)
        return self.wrapped.identify(hash)

    @deprecated_method(deprecated="1.7", removed="2.0")
    def genconfig(self, **kwds):
        config = self.wrapped.genconfig(**kwds)
        if config is None:
            raise RuntimeError(".genconfig() must return a string, not None")
        return self._wrap_hash(config)

    @deprecated_method(deprecated="1.7", removed="2.0")
    def genhash(self, secret, config, **kwds):
        # TODO: under 2.0, throw TypeError if config is None, rather than passing it through
        if config is not None:
            config = to_unicode(config, "ascii", "config/hash")
            config = self._unwrap_hash(config)
        return self._wrap_hash(self.wrapped.genhash(secret, config, **kwds))

    @deprecated_method(deprecated="1.7", removed="2.0", replacement=".hash()")
    def encrypt(self, secret, **kwds):
        return self.hash(secret, **kwds)

    def hash(self, secret, **kwds):
        return self._wrap_hash(self.wrapped.hash(secret, **kwds))

    def verify(self, secret, hash, **kwds):
        hash = to_unicode(hash, "ascii", "hash")
        hash = self._unwrap_hash(hash)
        return self.wrapped.verify(secret, hash, **kwds)

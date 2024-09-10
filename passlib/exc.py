"""passlib.exc -- exceptions & warnings raised by passlib"""


# =============================================================================
# exceptions
# =============================================================================
class UnknownBackendError(ValueError):
    """
    Error raised if multi-backend handler doesn't recognize backend name.
    Inherits from :exc:`ValueError`.

    .. versionadded:: 1.7
    """

    def __init__(self, hasher, backend):
        self.hasher = hasher
        self.backend = backend
        message = "%s: unknown backend: %r" % (hasher.name, backend)
        ValueError.__init__(self, message)


# XXX: add a PasslibRuntimeError as base for Missing/Internal/Security runtime errors?


class MissingBackendError(RuntimeError):
    """Error raised if multi-backend handler has no available backends;
    or if specifically requested backend is not available.

    :exc:`!MissingBackendError` derives
    from :exc:`RuntimeError`, since it usually indicates
    lack of an external library or OS feature.
    This is primarily raised by handlers which depend on
    external libraries (which is currently just
    :class:`~passlib.hash.bcrypt`).
    """


class InternalBackendError(RuntimeError):
    """
    Error raised if something unrecoverable goes wrong with backend call;
    such as if ``crypt.crypt()`` returning a malformed hash.

    .. versionadded:: 1.7.3
    """


class PasswordValueError(ValueError):
    """
    Error raised if a password can't be hashed / verified for various reasons.
    This exception derives from the builtin :exc:`!ValueError`.

    May be thrown directly when password violates internal invariants of hasher
    (e.g. some don't support NULL characters).  Hashers may also throw more specific subclasses,
    such as :exc:`!PasswordSizeError`.

    .. versionadded:: 1.7.3
    """

    pass


class PasswordSizeError(PasswordValueError):
    """
    Error raised if a password exceeds the maximum size allowed
    by Passlib (by default, 4096 characters); or if password exceeds
    a hash-specific size limitation.

    This exception derives from :exc:`PasswordValueError` (above).

    Many password hash algorithms take proportionately larger amounts of time and/or
    memory depending on the size of the password provided. This could present
    a potential denial of service (DOS) situation if a maliciously large
    password is provided to an application. Because of this, Passlib enforces
    a maximum size limit, but one which should be *much* larger
    than any legitimate password. :exc:`PasswordSizeError` derives
    from :exc:`!ValueError`.

    .. note::
        Applications wishing to use a different limit should set the
        ``PASSLIB_MAX_PASSWORD_SIZE`` environmental variable before
        Passlib is loaded. The value can be any large positive integer.

    .. attribute:: max_size

        indicates the maximum allowed size.

    .. versionadded:: 1.6
    """

    max_size = None

    def __init__(self, max_size, msg=None):
        self.max_size = max_size
        if msg is None:
            msg = "password exceeds maximum allowed size"
        PasswordValueError.__init__(self, msg)

    # this also prevents a glibc crypt segfault issue, detailed here ...
    # http://www.openwall.com/lists/oss-security/2011/11/15/1


class PasswordTruncateError(PasswordSizeError):
    """
    Error raised if password would be truncated by hash.
    This derives from :exc:`PasswordSizeError` (above).

    Hashers such as :class:`~passlib.hash.bcrypt` can be configured to raises
    this error by setting ``truncate_error=True``.

    .. attribute:: max_size

        indicates the maximum allowed size.

    .. versionadded:: 1.7
    """

    def __init__(self, cls, msg=None):
        if msg is None:
            msg = "Password too long (%s truncates to %d characters)" % (
                cls.name,
                cls.truncate_size,
            )
        PasswordSizeError.__init__(self, cls.truncate_size, msg)


class PasslibSecurityError(RuntimeError):
    """
    Error raised if critical security issue is detected
    (e.g. an attempt is made to use a vulnerable version of a bcrypt backend).

    .. versionadded:: 1.6.3
    """


class TokenError(ValueError):
    """
    Base error raised by v:mod:`passlib.totp` when
    a token can't be parsed / isn't valid / etc.
    Derives from :exc:`!ValueError`.

    Usually one of the more specific subclasses below will be raised:

    * :class:`MalformedTokenError` -- invalid chars, too few digits
    * :class:`InvalidTokenError` -- no match found
    * :class:`UsedTokenError` -- match found, but token already used

    .. versionadded:: 1.7
    """

    #: default message to use if none provided -- subclasses may fill this in
    _default_message = "Token not acceptable"

    def __init__(self, msg=None, *args, **kwds):
        if msg is None:
            msg = self._default_message
        ValueError.__init__(self, msg, *args, **kwds)


class MalformedTokenError(TokenError):
    """
    Error raised by :mod:`passlib.totp` when a token isn't formatted correctly
    (contains invalid characters, wrong number of digits, etc)
    """

    _default_message = "Unrecognized token"


class InvalidTokenError(TokenError):
    """
    Error raised by :mod:`passlib.totp` when a token is formatted correctly,
    but doesn't match any tokens within valid range.
    """

    _default_message = "Token did not match"


class UsedTokenError(TokenError):
    """
    Error raised by :mod:`passlib.totp` if a token is reused.
    Derives from :exc:`TokenError`.

    .. autoattribute:: expire_time

    .. versionadded:: 1.7
    """

    _default_message = "Token has already been used, please wait for another."

    #: optional value indicating when current counter period will end,
    #: and a new token can be generated.
    expire_time = None

    def __init__(self, *args, **kwds):
        self.expire_time = kwds.pop("expire_time", None)
        TokenError.__init__(self, *args, **kwds)


class UnknownHashError(ValueError):
    """
    Error raised by :class:`~passlib.crypto.lookup_hash` if hash name is not recognized.
    This exception derives from :exc:`!ValueError`.

    As of version 1.7.3, this may also be raised if hash algorithm is known,
    but has been disabled due to FIPS mode (message will include phrase "disabled for fips").

    As of version 1.7.4, this may be raised if a :class:`~passlib.context.CryptContext`
    is unable to identify the algorithm used by a password hash.

    .. versionadded:: 1.7

    .. versionchanged: 1.7.3
        added 'message' argument.

    .. versionchanged:: 1.7.4
        altered call signature.
    """

    def __init__(self, message=None, value=None):
        self.value = value
        if message is None:
            message = "unknown hash algorithm: %r" % value
        self.message = message
        ValueError.__init__(self, message, value)

    def __str__(self):
        return self.message


# =============================================================================
# warnings
# =============================================================================
class PasslibWarning(UserWarning):
    """base class for Passlib's user warnings,
    derives from the builtin :exc:`UserWarning`.

    .. versionadded:: 1.6
    """


# XXX: there's only one reference to this class, and it will go away in 2.0;
#      so can probably remove this along with this / roll this into PasslibHashWarning.
class PasslibConfigWarning(PasslibWarning):
    """Warning issued when non-fatal issue is found related to the configuration
    of a :class:`~passlib.context.CryptContext` instance.

    This occurs primarily in one of two cases:

    * The CryptContext contains rounds limits which exceed the hard limits
      imposed by the underlying algorithm.
    * An explicit rounds value was provided which exceeds the limits
      imposed by the CryptContext.

    In both of these cases, the code will perform correctly & securely;
    but the warning is issued as a sign the configuration may need updating.

    .. versionadded:: 1.6
    """


class PasslibHashWarning(PasslibWarning):
    """Warning issued when non-fatal issue is found with parameters
    or hash string passed to a passlib hash class.

    This occurs primarily in one of two cases:

    * A rounds value or other setting was explicitly provided which
      exceeded the handler's limits (and has been clamped
      by the :ref:`relaxed<relaxed-keyword>` flag).

    * A malformed hash string was encountered which (while parsable)
      should be re-encoded.

    .. versionadded:: 1.6
    """


class PasslibRuntimeWarning(PasslibWarning):
    """Warning issued when something unexpected happens during runtime.

    The fact that it's a warning instead of an error means Passlib
    was able to correct for the issue, but that it's anomalous enough
    that the developers would love to hear under what conditions it occurred.

    .. versionadded:: 1.6
    """


class PasslibSecurityWarning(PasslibWarning):
    """Special warning issued when Passlib encounters something
    that might affect security.

    .. versionadded:: 1.6
    """


# =============================================================================
# error constructors
#
# note: these functions are used by the hashes in Passlib to raise common
# error messages. They are currently just functions which return ValueError,
# rather than subclasses of ValueError, since the specificity isn't needed
# yet; and who wants to import a bunch of error classes when catching
# ValueError will do?
# =============================================================================


def _get_name(handler):
    return handler.name if handler else "<unnamed>"


# ------------------------------------------------------------------------
# generic helpers
# ------------------------------------------------------------------------
def type_name(value):
    """return pretty-printed string containing name of value's type"""
    cls = value.__class__
    if cls.__module__ and cls.__module__ not in ["__builtin__", "builtins"]:
        return "%s.%s" % (cls.__module__, cls.__name__)
    elif value is None:
        return "None"
    else:
        return cls.__name__


def ExpectedTypeError(value, expected, param):
    """error message when param was supposed to be one type, but found another"""
    # NOTE: value is never displayed, since it may sometimes be a password.
    name = type_name(value)
    return TypeError("%s must be %s, not %s" % (param, expected, name))


def ExpectedStringError(value, param):
    """error message when param was supposed to be str or bytes"""
    return ExpectedTypeError(value, "str or bytes", param)


# ------------------------------------------------------------------------
# hash/verify parameter errors
# ------------------------------------------------------------------------
def MissingDigestError(handler=None):
    """raised when verify() method gets passed config string instead of hash"""
    name = _get_name(handler)
    return ValueError("expected %s hash, got %s config string instead" % (name, name))


def NullPasswordError(handler=None):
    """raised by OS crypt() supporting hashes, which forbid NULLs in password"""
    name = _get_name(handler)
    return PasswordValueError("%s does not allow NULL bytes in password" % name)


# ------------------------------------------------------------------------
# errors when parsing hashes
# ------------------------------------------------------------------------
def InvalidHashError(handler=None):
    """error raised if unrecognized hash provided to handler"""
    return ValueError("not a valid %s hash" % _get_name(handler))


def MalformedHashError(handler=None, reason=None):
    """error raised if recognized-but-malformed hash provided to handler"""
    text = "malformed %s hash" % _get_name(handler)
    if reason:
        text = "%s (%s)" % (text, reason)
    return ValueError(text)


def ZeroPaddedRoundsError(handler=None):
    """error raised if hash was recognized but contained zero-padded rounds field"""
    return MalformedHashError(handler, "zero-padded rounds")


# ------------------------------------------------------------------------
# settings / hash component errors
# ------------------------------------------------------------------------
def ChecksumSizeError(handler, raw=False):
    """error raised if hash was recognized, but checksum was wrong size"""
    # TODO: if handler.use_defaults is set, this came from app-provided value,
    # not from parsing a hash string, might want different error msg.
    checksum_size = handler.checksum_size
    unit = "bytes" if raw else "chars"
    reason = "checksum must be exactly %d %s" % (checksum_size, unit)
    return MalformedHashError(handler, reason)


# =============================================================================
# sensitive info helpers
# =============================================================================

#: global flag, set temporarily by UTs to allow debug_only_repr() to display sensitive values.
ENABLE_DEBUG_ONLY_REPR = False


def debug_only_repr(value, param="hash"):
    """
    helper used to display sensitive data (hashes etc) within error messages.
    currently returns placeholder test UNLESS unittests are running,
    in which case the real value is displayed.

    mainly useful to prevent hashes / secrets from being exposed in production tracebacks;
    while still being visible from test failures.

    NOTE: api subject to change, may formalize this more in the future.
    """
    if ENABLE_DEBUG_ONLY_REPR or value is None or isinstance(value, bool):
        return repr(value)
    return "<%s %s value omitted>" % (param, type(value))


def CryptBackendError(
    handler,
    config,
    hash,  # *
    source="crypt.crypt()",
):
    """
    helper to generate standard message when ``crypt.crypt()`` returns invalid result.
    takes care of automatically masking contents of config & hash outside of UTs.
    """
    name = _get_name(handler)
    msg = "%s returned invalid %s hash: config=%s hash=%s" % (
        source,
        name,
        debug_only_repr(config),
        debug_only_repr(hash),
    )
    raise InternalBackendError(msg)


# =============================================================================
# eof
# =============================================================================

from passlib.context import LazyCryptContext
from passlib import registry

# local
__all__ = [
    "linux_context",
    "linux2_context",
    "openbsd_context",
    "netbsd_context",
    "freebsd_context",
    "host_context",
]


# known platform names - linux2

linux_context = linux2_context = LazyCryptContext(
    schemes=["sha512_crypt", "sha256_crypt", "md5_crypt", "des_crypt", "unix_disabled"],
    deprecated=["des_crypt"],
)


# known platform names -
#   freebsd2
#   freebsd3
#   freebsd4
#   freebsd5
#   freebsd6
#   freebsd7
#
#   netbsd1

# referencing source via -http://fxr.googlebit.com
# freebsd 6,7,8 - des, md5, bcrypt, bsd_nthash
# netbsd - des, ext, md5, bcrypt, sha1
# openbsd - des, ext, md5, bcrypt

freebsd_context = LazyCryptContext(
    ["bcrypt", "md5_crypt", "bsd_nthash", "des_crypt", "unix_disabled"]
)

openbsd_context = LazyCryptContext(
    ["bcrypt", "md5_crypt", "bsdi_crypt", "des_crypt", "unix_disabled"]
)

netbsd_context = LazyCryptContext(
    ["bcrypt", "sha1_crypt", "md5_crypt", "bsdi_crypt", "des_crypt", "unix_disabled"]
)

# XXX: include darwin in this list? it's got a BSD crypt variant,
# but that's not what it uses for user passwords.

if registry.os_crypt_present:
    # NOTE: this is basically mimicing the output of os crypt(),
    # except that it uses passlib's (usually stronger) defaults settings,
    # and can be inspected and used much more flexibly.

    def _iter_os_crypt_schemes():
        """helper which iterates over supported os_crypt schemes"""
        out = registry.get_supported_os_crypt_schemes()
        if out:
            # only offer disabled handler if there's another scheme in front,
            # as this can't actually hash any passwords
            out += ("unix_disabled",)
        return out

    host_context = LazyCryptContext(_iter_os_crypt_schemes())


# known platform strings -
# aix3
# aix4
# atheos
# beos5
# darwin
# generic
# hp-ux11
# irix5
# irix6
# mac
# next3
# os2emx
# riscos
# sunos5
# unixware7
